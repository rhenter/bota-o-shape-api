from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core.models import AuditEvent
from apps.food.services import food_snapshot
from apps.tenancy.models import ConsentRecord, DietitianStudentAssignment, RoleAssignment
from apps.tenancy.services import (
    get_membership,
    require_student_scope,
    require_verified_dietitian,
    roles_for,
)

from .models import (
    HydrationLog,
    MealLog,
    MealPlan,
    MealPlanCheckIn,
    NutritionMessage,
    NutritionProfile,
)
from .serializers import (
    CheckInSerializer,
    HydrationLogSerializer,
    MealLogSerializer,
    MealPlanSerializer,
    MealPlanVersionSerializer,
    NutritionMessageSerializer,
    NutritionProfileSerializer,
    StudentMealPlanSerializer,
    create_slots,
)


class MealPlanViewSet(viewsets.ModelViewSet):
    serializer_class = MealPlanSerializer
    queryset = MealPlan.objects.all()
    filterset_fields = ("student", "status")
    http_method_names = ("get", "post", "put", "patch", "head", "options")

    def perform_update(self, serializer):
        membership = get_membership(self.request)
        require_verified_dietitian(membership)
        if serializer.instance.status != MealPlan.Status.DRAFT:
            raise ValidationError("Planos publicados são imutáveis; crie uma nova versão.")
        serializer.save()

    def get_serializer_class(self):
        if getattr(self, "swagger_fake_view", False):
            return MealPlanSerializer
        membership = get_membership(self.request)
        if RoleAssignment.Role.STUDENT in roles_for(membership) and self.action in {
            "list",
            "retrieve",
        }:
            return StudentMealPlanSerializer
        return MealPlanSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        queryset = MealPlan.objects.filter(tenant=membership.tenant).prefetch_related(
            "versions__meal_slots__foods__substitutions"
        )
        roles = roles_for(membership)
        if RoleAssignment.Role.STUDENT in roles:
            queryset = queryset.filter(student=self.request.user, status=MealPlan.Status.PUBLISHED)
        elif RoleAssignment.Role.DIETITIAN not in roles:
            queryset = queryset.none()
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == "POST":
            context["credential"] = require_verified_dietitian(get_membership(self.request))
        return context

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        require_verified_dietitian(membership)
        student = serializer.validated_data["student"]
        require_student_scope(membership, student.id, DietitianStudentAssignment, "dietitian")
        if not ConsentRecord.objects.filter(
            tenant=membership.tenant,
            subject=student,
            purpose="nutrition_plan",
            granted=True,
            revoked_at__isnull=True,
        ).exists():
            raise ValidationError("Consentimento nutricional ativo é obrigatório.")
        serializer.save(tenant=membership.tenant, author=self.request.user)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        membership = get_membership(request)
        require_verified_dietitian(membership)
        from apps.billing.services import require_commercial_write

        require_commercial_write(membership.tenant, "nutrition")
        plan = self.get_object()
        version = plan.versions.filter(published_at__isnull=True).order_by("-version").first()
        if not version:
            return Response({"detail": "Não há rascunho para publicar."}, status=400)
        version.published_at = timezone.now()
        version.save(update_fields=("published_at", "updated_at"))
        plan.active_version = version
        plan.status = MealPlan.Status.PUBLISHED
        plan.save(update_fields=("active_version", "status", "updated_at"))
        AuditEvent.objects.create(
            tenant=membership.tenant,
            actor=request.user,
            action="meal_plan.published",
            target_id=str(plan.id),
            metadata={"version": version.version},
        )
        return Response(self.get_serializer(plan).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def revise(self, request, pk=None):
        membership = get_membership(request)
        credential = require_verified_dietitian(membership)
        plan = self.get_object()
        serializer = MealPlanVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        slots = data.pop("meal_slots")
        next_version = (plan.versions.aggregate(value=Max("version"))["value"] or 0) + 1
        version = plan.versions.create(
            tenant=membership.tenant,
            author=request.user,
            version=next_version,
            crn=credential.registration_number,
            crn_state=credential.state,
            **data,
        )
        create_slots(version, slots)
        return Response(MealPlanVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class StudentOwnedViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        return self.queryset.filter(tenant=membership.tenant, student=self.request.user)

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        if RoleAssignment.Role.STUDENT not in roles_for(membership):
            raise PermissionDenied("Somente o aluno registra este recurso.")
        serializer.save(tenant=membership.tenant, student=self.request.user)


class MealLogViewSet(StudentOwnedViewSet):
    queryset = MealLog.objects.all()
    serializer_class = MealLogSerializer

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        if RoleAssignment.Role.STUDENT not in roles_for(membership):
            raise PermissionDenied("Somente o aluno registra este recurso.")
        food = serializer.validated_data.get("food")
        grams = serializer.validated_data.get("grams")
        if food and not grams:
            raise ValidationError({"grams": "Alimento catalogado exige gramas."})
        serializer.save(
            tenant=membership.tenant,
            student=self.request.user,
            nutrition_snapshot=food_snapshot(food, grams) if food else {},
        )


class HydrationLogViewSet(StudentOwnedViewSet):
    queryset = HydrationLog.objects.all()
    serializer_class = HydrationLogSerializer


class CheckInViewSet(StudentOwnedViewSet):
    queryset = MealPlanCheckIn.objects.all()
    serializer_class = CheckInSerializer

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        version = serializer.validated_data["version"]
        if (
            version.plan.student_id != self.request.user.id
            or version.plan.tenant_id != membership.tenant_id
        ):
            raise PermissionDenied("Versão não atribuída a este aluno.")
        super().perform_create(serializer)


class NutritionProfileViewSet(StudentOwnedViewSet):
    queryset = NutritionProfile.objects.all()
    serializer_class = NutritionProfileSerializer


class NutritionMessageViewSet(viewsets.ModelViewSet):
    queryset = NutritionMessage.objects.all()
    serializer_class = NutritionMessageSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        queryset = self.queryset.filter(tenant=membership.tenant)
        roles = roles_for(membership)
        if RoleAssignment.Role.STUDENT in roles:
            return queryset.filter(student=self.request.user)
        if RoleAssignment.Role.COACH in roles:
            return queryset.filter(shared_with_coach=True)
        if RoleAssignment.Role.DIETITIAN in roles:
            return queryset.filter(student__assigned_dietitians__dietitian=self.request.user)
        return queryset.none()

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(tenant=membership.tenant, author=self.request.user)
