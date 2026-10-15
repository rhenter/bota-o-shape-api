from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.models import AuditEvent

from .models import (
    CoachStudentAssignment,
    ConsentRecord,
    DietitianStudentAssignment,
    GymUnit,
    Invitation,
    Membership,
    ProfessionalCredential,
    RoleAssignment,
    Tenant,
)
from .serializers import (
    CoachStudentAssignmentSerializer,
    ConsentRecordSerializer,
    DietitianStudentAssignmentSerializer,
    GymUnitSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    MembershipSerializer,
    OwnerRegistrationSerializer,
    ProfessionalCredentialSerializer,
    TenantSerializer,
)
from .services import get_membership, require_roles


class OwnerRegistrationView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = OwnerRegistrationSerializer

    def post(self, request):
        serializer = OwnerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class InvitationAcceptView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = InvitationAcceptSerializer

    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class TenantViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Tenant.objects.none()
        tenant_ids = Membership.objects.filter(
            user=self.request.user, status=Membership.Status.ACTIVE
        ).values("tenant_id")
        return Tenant.objects.filter(id__in=tenant_ids)


class GymUnitViewSet(viewsets.ModelViewSet):
    serializer_class = GymUnitSerializer
    queryset = GymUnit.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        return GymUnit.objects.filter(tenant=membership.tenant)

    def perform_create(self, serializer):
        membership = require_roles(
            self.request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN
        )
        from apps.billing.services import enforce_limit

        enforce_limit(
            membership.tenant,
            "units",
            GymUnit.objects.filter(tenant=membership.tenant, is_active=True).count(),
        )
        serializer.save(tenant=membership.tenant)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=("is_active", "updated_at"))


class MembershipViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MembershipSerializer
    queryset = Membership.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        roles = set(membership.role_assignments.values_list("role", flat=True))
        if roles.intersection({RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN}):
            return Membership.objects.filter(tenant=membership.tenant).select_related("user")
        return Membership.objects.filter(pk=membership.pk).select_related("user")

    @action(detail=False, methods=["post"])
    def invite(self, request):
        membership = require_roles(request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN)
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.billing.services import enforce_limit

        enforce_limit(
            membership.tenant,
            "active_students"
            if RoleAssignment.Role.STUDENT in serializer.validated_data["roles"]
            else "team_members",
            Membership.objects.filter(
                tenant=membership.tenant, status=Membership.Status.ACTIVE
            ).count(),
        )
        invitation, token = Invitation.issue(
            tenant=membership.tenant, invited_by=request.user, **serializer.validated_data
        )
        send_mail(
            "Convite — Bota o Shape",
            f"Use este token para aceitar o convite: {token}",
            None,
            [invitation.email],
        )
        AuditEvent.objects.create(
            tenant=membership.tenant,
            actor=request.user,
            action="invitation.created",
            target_id=str(invitation.id),
            metadata={"roles": invitation.roles},
        )
        response = {"id": invitation.id}
        if settings.DEBUG:
            response["token"] = token
        return Response(response, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def archive(self, request, pk=None):
        current = require_roles(request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN)
        target = self.get_object()
        if target.tenant_id != current.tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        target.status = Membership.Status.ARCHIVED
        target.archived_at = timezone.now()
        target.save(update_fields=("status", "archived_at", "updated_at"))
        AuditEvent.objects.create(
            tenant=current.tenant,
            actor=request.user,
            action="membership.archived",
            target_id=str(target.id),
        )
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        current = require_roles(request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN)
        target = self.get_object()
        target.status = Membership.Status.ACTIVE
        target.archived_at = None
        target.save(update_fields=("status", "archived_at", "updated_at"))
        AuditEvent.objects.create(
            tenant=current.tenant,
            actor=request.user,
            action="membership.restored",
            target_id=str(target.id),
        )
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["put"], url_path="roles")
    @transaction.atomic
    def set_roles(self, request, pk=None):
        current = require_roles(request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN)
        target = self.get_object()
        roles = request.data.get("roles", [])
        from .services import validate_roles

        validate_roles(roles)
        if not roles:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"roles": "Informe ao menos um papel."})
        if (
            target.role_assignments.filter(role=RoleAssignment.Role.OWNER).exists()
            and RoleAssignment.Role.OWNER not in roles
            and Membership.objects.filter(
                tenant=current.tenant,
                status=Membership.Status.ACTIVE,
                role_assignments__role=RoleAssignment.Role.OWNER,
            ).count()
            == 1
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"roles": "A academia precisa manter ao menos um owner."})
        target.role_assignments.exclude(role__in=roles).delete()
        RoleAssignment.objects.bulk_create(
            [RoleAssignment(membership=target, role=role) for role in roles],
            ignore_conflicts=True,
        )
        AuditEvent.objects.create(
            tenant=current.tenant,
            actor=request.user,
            action="membership.roles_changed",
            target_id=str(target.id),
            metadata={"roles": roles},
        )
        return Response(self.get_serializer(target).data)


class TenantAdminModelViewSet(viewsets.ModelViewSet):
    tenant_user_fields = ()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = require_roles(
            self.request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN
        )
        return self.queryset.filter(tenant=membership.tenant)

    def perform_create(self, serializer):
        membership = require_roles(
            self.request, RoleAssignment.Role.OWNER, RoleAssignment.Role.ADMIN
        )
        for field in self.tenant_user_fields:
            user = serializer.validated_data[field]
            if not Membership.objects.filter(
                tenant=membership.tenant,
                user=user,
                status=Membership.Status.ACTIVE,
            ).exists():
                from rest_framework.exceptions import ValidationError

                raise ValidationError({field: "Usuário fora da academia ativa."})
        serializer.save(tenant=membership.tenant)


class ProfessionalCredentialViewSet(TenantAdminModelViewSet):
    queryset = ProfessionalCredential.objects.all()
    serializer_class = ProfessionalCredentialSerializer
    tenant_user_fields = ("professional",)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        credential = self.get_object()
        credential.verified_at = timezone.now()
        credential.verified_by = request.user
        credential.save(update_fields=("verified_at", "verified_by", "updated_at"))
        return Response(self.get_serializer(credential).data)


class CoachStudentAssignmentViewSet(TenantAdminModelViewSet):
    queryset = CoachStudentAssignment.objects.all()
    serializer_class = CoachStudentAssignmentSerializer
    tenant_user_fields = ("coach", "student")


class DietitianStudentAssignmentViewSet(TenantAdminModelViewSet):
    queryset = DietitianStudentAssignment.objects.all()
    serializer_class = DietitianStudentAssignmentSerializer
    tenant_user_fields = ("dietitian", "student")


class ConsentRecordViewSet(viewsets.ModelViewSet):
    queryset = ConsentRecord.objects.all()
    serializer_class = ConsentRecordSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        roles = set(membership.role_assignments.values_list("role", flat=True))
        queryset = self.queryset.filter(tenant=membership.tenant)
        if RoleAssignment.Role.STUDENT in roles:
            queryset = queryset.filter(subject=self.request.user)
        return queryset

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        roles = set(membership.role_assignments.values_list("role", flat=True))
        subject = serializer.validated_data["subject"]
        if not Membership.objects.filter(
            tenant=membership.tenant,
            user=subject,
            status=Membership.Status.ACTIVE,
        ).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"subject": "Usuário fora da academia ativa."})
        if RoleAssignment.Role.STUDENT in roles and subject != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("O aluno só pode registrar o próprio consentimento.")
        serializer.save(tenant=membership.tenant)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        consent = self.get_object()
        consent.granted = False
        consent.revoked_at = timezone.now()
        consent.save(update_fields=("granted", "revoked_at", "updated_at"))
        return Response(self.get_serializer(consent).data)
