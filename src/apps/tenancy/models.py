import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel, UUIDModel


class Tenant(UUIDModel):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    cnpj = models.CharField(max_length=14, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class GymUnit(TenantScopedModel):
    name = models.CharField(max_length=150)
    address = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("tenant", "name"), name="unique_unit_name")]


class Membership(TenantScopedModel):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INVITED)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("tenant", "user"), name="unique_tenant_member")
        ]


class RoleAssignment(UUIDModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        COACH = "coach", "Coach"
        DIETITIAN = "dietitian", "Dietitian"
        STUDENT = "student", "Student"
        BILLING_MANAGE = "billing.manage", "Manage billing"

    membership = models.ForeignKey(
        Membership, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.CharField(max_length=32, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("membership", "role"), name="unique_member_role")
        ]


class ProfessionalCredential(TenantScopedModel):
    class Kind(models.TextChoices):
        CRN = "crn", "CRN"
        CREF = "cref", "CREF"

    professional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    registration_number = models.CharField(max_length=50)
    state = models.CharField(max_length=2)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="credentials_verified",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "kind", "registration_number", "state"), name="unique_credential"
            )
        ]


class CoachStudentAssignment(TenantScopedModel):
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="coach_assignments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_coaches"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "coach", "student"), name="unique_coach_student"
            )
        ]


class DietitianStudentAssignment(TenantScopedModel):
    dietitian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dietitian_assignments"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_dietitians"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "dietitian", "student"), name="unique_dietitian_student"
            )
        ]


class ConsentRecord(TenantScopedModel):
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="consents"
    )
    purpose = models.CharField(max_length=100)
    granted = models.BooleanField(default=True)
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=("tenant", "subject", "purpose", "granted"))]


class Invitation(TenantScopedModel):
    email = models.EmailField()
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    token_digest = models.CharField(max_length=64, unique=True)
    roles = models.JSONField(default=list)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, *, tenant, email, invited_by, roles, lifetime_hours=48):
        token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            tenant=tenant,
            email=email.lower(),
            invited_by=invited_by,
            roles=roles,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=lifetime_hours),
        )
        return invitation, token

    @classmethod
    def from_token(cls, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        return cls.objects.filter(
            token_digest=digest, accepted_at__isnull=True, expires_at__gt=timezone.now()
        ).first()
