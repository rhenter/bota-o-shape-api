import uuid

from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TenantScopedModel(UUIDModel):
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT)

    class Meta:
        abstract = True


class AuditEvent(UUIDModel):
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("tenant", "action", "created_at"))]


class DataSubjectRequest(TenantScopedModel):
    class Kind(models.TextChoices):
        EXPORT = "export", "Export"
        DELETION = "deletion", "Deletion or anonymization"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        REVIEWING = "reviewing", "Reviewing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"

    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="data_requests_made"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    retention_reason = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
