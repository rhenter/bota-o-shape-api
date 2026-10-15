from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditEvent
from apps.tenancy.models import CoachStudentAssignment, RoleAssignment
from apps.tenancy.services import get_membership, require_roles, require_student_scope, roles_for

from .models import (
    Equipment,
    Exercise,
    MuscleGroup,
    WorkoutAssignment,
    WorkoutSession,
    WorkoutTemplate,
)
from .serializers import (
    EquipmentSerializer,
    ExerciseSerializer,
    MuscleGroupSerializer,
    WorkoutAssignmentSerializer,
    WorkoutSessionSerializer,
    WorkoutTemplateSerializer,
)


class TenantModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        return self.queryset.filter(tenant=membership.tenant)

    def perform_create(self, serializer):
        membership = require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        serializer.save(tenant=membership.tenant)


class EquipmentViewSet(TenantModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    search_fields = ("name",)


class MuscleGroupViewSet(TenantModelViewSet):
    queryset = MuscleGroup.objects.all()
    serializer_class = MuscleGroupSerializer
    search_fields = ("name",)


class ExerciseViewSet(TenantModelViewSet):
    queryset = Exercise.objects.prefetch_related(
        "equipment", "primary_muscles", "secondary_muscles"
    )
    serializer_class = ExerciseSerializer
    filterset_fields = ("tracking_type", "review_status", "equipment", "primary_muscles")
    search_fields = ("name", "description")

    def perform_create(self, serializer):
        membership = require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        for field in ("equipment", "primary_muscles", "secondary_muscles"):
            if any(
                item.tenant_id != membership.tenant_id
                for item in serializer.validated_data.get(field, [])
            ):
                from rest_framework.exceptions import ValidationError

                raise ValidationError({field: "Todos os itens devem pertencer à academia ativa."})
        serializer.save(tenant=membership.tenant)


class WorkoutTemplateViewSet(TenantModelViewSet):
    queryset = WorkoutTemplate.objects.prefetch_related(
        "days__exercises__sets", "days__exercises__exercise"
    )
    serializer_class = WorkoutTemplateSerializer
    filterset_fields = ("status", "level", "author")
    search_fields = ("name", "objective")
    http_method_names = ("get", "post", "put", "patch", "head", "options")

    def perform_create(self, serializer):
        membership = require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        serializer.save(tenant=membership.tenant, author=self.request.user)

    def perform_update(self, serializer):
        require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        if serializer.instance.status != WorkoutTemplate.Status.DRAFT:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Versões publicadas são imutáveis; crie uma revisão.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        membership = require_roles(
            request, RoleAssignment.Role.COACH, RoleAssignment.Role.ADMIN, RoleAssignment.Role.OWNER
        )
        template = self.get_object()
        from apps.billing.services import require_commercial_write

        require_commercial_write(membership.tenant, "workouts")
        if template.status != WorkoutTemplate.Status.DRAFT:
            return Response({"detail": "Somente rascunhos podem ser publicados."}, status=400)
        template.status = WorkoutTemplate.Status.PUBLISHED
        template.published_at = timezone.now()
        template.save(update_fields=("status", "published_at", "updated_at"))
        AuditEvent.objects.create(
            tenant=membership.tenant,
            actor=request.user,
            action="workout.published",
            target_id=str(template.id),
        )
        return Response(self.get_serializer(template).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def revise(self, request, pk=None):
        original = self.get_object()
        require_roles(
            request, RoleAssignment.Role.COACH, RoleAssignment.Role.ADMIN, RoleAssignment.Role.OWNER
        )
        clone = WorkoutTemplate.objects.create(
            tenant=original.tenant,
            name=original.name,
            objective=original.objective,
            level=original.level,
            notes=original.notes,
            version=original.version + 1,
            author=request.user,
            supersedes=original,
        )
        from .models import SetPrescription, WorkoutDay, WorkoutExercise

        for day in original.days.all():
            cloned_day = WorkoutDay.objects.create(
                tenant=original.tenant, template=clone, name=day.name, order=day.order
            )
            for exercise in day.exercises.all():
                cloned_exercise = WorkoutExercise.objects.create(
                    tenant=original.tenant,
                    day=cloned_day,
                    exercise=exercise.exercise,
                    variant=exercise.variant,
                    alternative=exercise.alternative,
                    order=exercise.order,
                    coach_observation=exercise.coach_observation,
                )
                SetPrescription.objects.bulk_create(
                    [
                        SetPrescription(
                            tenant=original.tenant,
                            workout_exercise=cloned_exercise,
                            order=item.order,
                            repetitions_min=item.repetitions_min,
                            repetitions_max=item.repetitions_max,
                            load_kg=item.load_kg,
                            duration_seconds=item.duration_seconds,
                            distance_meters=item.distance_meters,
                            rest_seconds=item.rest_seconds,
                            rpe=item.rpe,
                            rir=item.rir,
                            cadence=item.cadence,
                            note=item.note,
                        )
                        for item in exercise.sets.all()
                    ]
                )
        serializer = self.get_serializer(clone)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkoutAssignmentViewSet(TenantModelViewSet):
    queryset = WorkoutAssignment.objects.select_related(
        "template", "student", "assigned_by"
    ).prefetch_related("template__days__exercises__sets")
    serializer_class = WorkoutAssignmentSerializer
    filterset_fields = ("student", "is_active")
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        queryset = self.queryset.filter(tenant=membership.tenant)
        if RoleAssignment.Role.STUDENT in roles_for(membership):
            queryset = queryset.filter(student=self.request.user)
        return queryset

    def perform_create(self, serializer):
        membership = require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        student = serializer.validated_data["student"]
        require_student_scope(membership, student.id, CoachStudentAssignment, "coach")
        template = serializer.validated_data["template"]
        if (
            template.tenant_id != membership.tenant_id
            or template.status != WorkoutTemplate.Status.PUBLISHED
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError("O treino precisa ser uma versão publicada da academia ativa.")
        serializer.save(tenant=membership.tenant, assigned_by=self.request.user)


class WorkoutSessionViewSet(viewsets.ModelViewSet):
    serializer_class = WorkoutSessionSerializer
    queryset = WorkoutSession.objects.all()
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        queryset = WorkoutSession.objects.filter(tenant=membership.tenant).prefetch_related(
            "exercise_logs__set_logs"
        )
        if RoleAssignment.Role.STUDENT in roles_for(membership):
            queryset = queryset.filter(student=self.request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        membership = require_roles(request, RoleAssignment.Role.STUDENT)
        key = request.data.get("idempotency_key")
        existing = WorkoutSession.objects.filter(
            tenant=membership.tenant, student=request.user, idempotency_key=key
        ).first()
        if existing:
            return Response(self.get_serializer(existing).data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.validated_data["assignment"]
        today = timezone.localdate()
        if assignment.tenant_id != membership.tenant_id or assignment.student_id != request.user.id:
            return Response({"detail": "Atribuição inválida."}, status=403)
        for exercise_log in serializer.validated_data.get("exercise_logs", []):
            prescribed = exercise_log["workout_exercise"]
            if prescribed.day.template_id != assignment.template_id:
                return Response({"detail": "Exercício fora do treino atribuído."}, status=400)
            for set_log in exercise_log.get("set_logs", []):
                prescription = set_log.get("prescription")
                if prescription and prescription.workout_exercise_id != prescribed.id:
                    return Response({"detail": "Série fora do exercício informado."}, status=400)
        if today < assignment.starts_on or (assignment.ends_on and today > assignment.ends_on):
            return Response({"detail": "Treino fora da janela permitida."}, status=400)
        serializer.save(tenant=membership.tenant, student=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
