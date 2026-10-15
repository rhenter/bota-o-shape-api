from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel
from apps.tenancy.models import ConsentRecord


class MeasurementProtocol(TenantScopedModel):
    name = models.CharField(max_length=150)
    version = models.CharField(max_length=40)
    method = models.CharField(max_length=80)
    sites = models.JSONField(default=list)
    equation_metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name", "version"), name="unique_protocol_version"
            )
        ]


class Assessment(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWED = "reviewed", "Reviewed"
        COMPLETED = "completed", "Completed"
        RELEASED = "released", "Released"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessments"
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessments_made"
    )
    assessed_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    device = models.JSONField(default=dict, blank=True)
    preparation_conditions = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    consent = models.ForeignKey(ConsentRecord, on_delete=models.PROTECT)
    released_at = models.DateTimeField(null=True, blank=True)


class Measurement(TenantScopedModel):
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="measurements"
    )
    metric = models.CharField(max_length=100)
    raw_value = models.DecimalField(max_digits=12, decimal_places=4)
    unit = models.CharField(max_length=24)
    side = models.CharField(max_length=16, blank=True)
    anatomical_site = models.CharField(max_length=120, blank=True)
    method = models.CharField(max_length=80)
    protocol = models.ForeignKey(
        MeasurementProtocol, null=True, blank=True, on_delete=models.PROTECT
    )
    origin = models.CharField(max_length=80, default="manual")
    equation_metadata = models.JSONField(default=dict, blank=True)
    possible_error = models.BooleanField(default=False)

    def compatibility_key(self):
        return (
            self.metric,
            self.unit,
            self.side,
            self.anatomical_site,
            self.method,
            self.protocol_id,
        )


class AssessmentReport(TenantScopedModel):
    assessment = models.OneToOneField(Assessment, on_delete=models.PROTECT, related_name="report")
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    comparisons = models.JSONField(default=list)
    professional_interpretation = models.TextField(blank=True)
    released_to_student = models.BooleanField(default=False)
