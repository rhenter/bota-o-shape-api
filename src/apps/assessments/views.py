from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditEvent
from apps.tenancy.models import CoachStudentAssignment, RoleAssignment
from apps.tenancy.services import get_membership, require_roles, require_student_scope, roles_for

from .models import Assessment, AssessmentReport, MeasurementProtocol
from .serializers import (
    AssessmentReportSerializer,
    AssessmentSerializer,
    MeasurementProtocolSerializer,
)
from .services import build_comparisons


class ProtocolViewSet(viewsets.ModelViewSet):
    serializer_class = MeasurementProtocolSerializer
    queryset = MeasurementProtocol.objects.all()
    search_fields = ("name", "method")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        return MeasurementProtocol.objects.filter(tenant=get_membership(self.request).tenant)

    def perform_create(self, serializer):
        membership = require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        serializer.save(tenant=membership.tenant)


class AssessmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer
    queryset = Assessment.objects.all()
    filterset_fields = ("student", "status")
    http_method_names = ("get", "post", "put", "patch", "head", "options")

    def perform_update(self, serializer):
        require_roles(
            self.request,
            RoleAssignment.Role.COACH,
            RoleAssignment.Role.ADMIN,
            RoleAssignment.Role.OWNER,
        )
        if serializer.instance.status in (Assessment.Status.COMPLETED, Assessment.Status.RELEASED):
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Avaliações concluídas são imutáveis.")
        serializer.save()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        queryset = Assessment.objects.filter(tenant=membership.tenant).prefetch_related(
            "measurements"
        )
        if RoleAssignment.Role.STUDENT in roles_for(membership):
            queryset = queryset.filter(student=self.request.user, status=Assessment.Status.RELEASED)
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
        consent = serializer.validated_data["consent"]
        if (
            consent.tenant_id != membership.tenant_id
            or consent.subject_id != student.id
            or not consent.granted
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Consentimento ativo é obrigatório.")
        for measurement in serializer.validated_data.get("measurements", []):
            protocol = measurement.get("protocol")
            if protocol and protocol.tenant_id != membership.tenant_id:
                raise ValidationError({"measurements": "Protocolo fora da academia ativa."})
        serializer.save(tenant=membership.tenant, evaluator=self.request.user)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        membership = require_roles(
            request, RoleAssignment.Role.COACH, RoleAssignment.Role.ADMIN, RoleAssignment.Role.OWNER
        )
        assessment = self.get_object()
        requested = request.data.get("status")
        allowed = {
            Assessment.Status.DRAFT: Assessment.Status.REVIEWED,
            Assessment.Status.REVIEWED: Assessment.Status.COMPLETED,
            Assessment.Status.COMPLETED: Assessment.Status.RELEASED,
        }
        if allowed.get(assessment.status) != requested:
            return Response({"detail": "Transição inválida."}, status=400)
        if requested == Assessment.Status.RELEASED:
            from apps.billing.services import require_commercial_write

            require_commercial_write(membership.tenant, "assessments")
        assessment.status = requested
        fields = ["status", "updated_at"]
        if requested == Assessment.Status.RELEASED:
            assessment.released_at = timezone.now()
            fields.append("released_at")
            report, _ = AssessmentReport.objects.update_or_create(
                tenant=membership.tenant,
                assessment=assessment,
                defaults={
                    "generated_by": request.user,
                    "comparisons": build_comparisons(assessment),
                    "released_to_student": True,
                },
            )
            AuditEvent.objects.create(
                tenant=membership.tenant,
                actor=request.user,
                action="assessment.released",
                target_id=str(assessment.id),
            )
        assessment.save(update_fields=fields)
        return Response(self.get_serializer(assessment).data)

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        assessment = self.get_object()
        if not hasattr(assessment, "report"):
            return Response({"detail": "Relatório ainda não gerado."}, status=404)
        return Response(AssessmentReportSerializer(assessment.report).data)
