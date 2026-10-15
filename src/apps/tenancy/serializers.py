from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

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
from .services import validate_roles


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "name", "legal_name", "cnpj", "is_active", "created_at")
        read_only_fields = ("id", "is_active", "created_at")


class GymUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymUnit
        exclude = ("tenant",)
        read_only_fields = ("id", "created_at", "updated_at")


class MembershipSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "email", "status", "roles", "created_at")
        read_only_fields = fields

    def get_roles(self, obj) -> list[str]:
        return list(obj.role_assignments.values_list("role", flat=True))


class ProfessionalCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalCredential
        exclude = ("tenant", "verified_by")
        read_only_fields = ("verified_at",)


class CoachStudentAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachStudentAssignment
        exclude = ("tenant",)


class DietitianStudentAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietitianStudentAssignment
        exclude = ("tenant",)


class ConsentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        exclude = ("tenant",)
        read_only_fields = ("granted_at", "revoked_at")


class OwnerRegistrationSerializer(serializers.Serializer):
    tenant_name = serializers.CharField(max_length=200)
    cnpj = serializers.CharField(max_length=14, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if get_user_model().objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Já existe uma conta com este e-mail.")
        return value.lower()

    def validate_cnpj(self, value):
        digits = "".join(character for character in value if character.isdigit())
        if value and len(digits) != 14:
            raise serializers.ValidationError("CNPJ deve conter 14 dígitos.")
        if digits and Tenant.objects.filter(cnpj=digits).exists():
            raise serializers.ValidationError("Já existe uma academia com este CNPJ.")
        return digits

    @transaction.atomic
    def create(self, validated_data):
        user_model = get_user_model()
        email = validated_data["email"].lower()
        user = user_model.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data.get("last_name", ""),
        )
        tenant = Tenant.objects.create(
            name=validated_data["tenant_name"], cnpj=validated_data.get("cnpj") or None
        )
        membership = Membership.objects.create(
            tenant=tenant, user=user, status=Membership.Status.ACTIVE
        )
        RoleAssignment.objects.bulk_create(
            [
                RoleAssignment(membership=membership, role=RoleAssignment.Role.OWNER),
                RoleAssignment(membership=membership, role=RoleAssignment.Role.ADMIN),
                RoleAssignment(membership=membership, role=RoleAssignment.Role.BILLING_MANAGE),
            ]
        )
        from apps.billing.models import AcademySubscription, BillingPlan

        pilot_plan, _ = BillingPlan.objects.get_or_create(
            code="pilot",
            defaults={
                "name": "Piloto provisionado",
                "features": ["workouts", "assessments", "nutrition"],
                "limits": {},
            },
        )
        AcademySubscription.objects.create(
            tenant=tenant,
            plan=pilot_plan,
            status=AcademySubscription.Status.PILOT,
            billing_cycle="pilot",
        )
        AuditEvent.objects.create(tenant=tenant, actor=user, action="tenant.owner_registered")
        return membership


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    roles = serializers.ListField(child=serializers.CharField(), allow_empty=False)

    def validate_roles(self, value):
        validate_roles(value)
        return list(dict.fromkeys(value))


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        invitation = Invitation.from_token(validated_data["token"])
        if not invitation:
            raise serializers.ValidationError({"token": "Convite inválido ou expirado."})
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=invitation.email,
            defaults={
                "username": invitation.email,
                "first_name": validated_data["first_name"],
                "last_name": validated_data.get("last_name", ""),
            },
        )
        if created:
            user.set_password(validated_data["password"])
            user.save(update_fields=("password",))
        membership, _ = Membership.objects.update_or_create(
            tenant=invitation.tenant,
            user=user,
            defaults={"status": Membership.Status.ACTIVE, "archived_at": None},
        )
        RoleAssignment.objects.bulk_create(
            [RoleAssignment(membership=membership, role=role) for role in invitation.roles],
            ignore_conflicts=True,
        )
        from django.utils import timezone

        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=("accepted_at",))
        AuditEvent.objects.create(
            tenant=invitation.tenant,
            actor=user,
            action="invitation.accepted",
            target_id=str(invitation.id),
        )
        return membership
