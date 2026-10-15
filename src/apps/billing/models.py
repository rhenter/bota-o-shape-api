from django.db import models

from apps.core.models import TenantScopedModel, UUIDModel


class BillingPlan(UUIDModel):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    version = models.PositiveIntegerField(default=1)
    features = models.JSONField(default=list)
    limits = models.JSONField(default=dict)
    price_reference = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)


class AcademySubscription(TenantScopedModel):
    class Status(models.TextChoices):
        PILOT = "pilot", "Pilot"
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        DELINQUENT = "delinquent", "Delinquent"
        CANCEL_SCHEDULED = "cancel_scheduled", "Cancellation scheduled"
        CANCELLED = "cancelled", "Cancelled"
        SUSPENDED = "suspended", "Suspended"

    plan = models.ForeignKey(BillingPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, choices=Status.choices)
    billing_cycle = models.CharField(max_length=24, default="monthly")
    provider = models.CharField(max_length=60, blank=True)
    external_customer_id = models.CharField(max_length=150, blank=True)
    external_subscription_id = models.CharField(max_length=150, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    cancel_at = models.DateTimeField(null=True, blank=True)
    billing_details = models.JSONField(default=dict, blank=True)


class Invoice(TenantScopedModel):
    subscription = models.ForeignKey(
        AcademySubscription, on_delete=models.PROTECT, related_name="invoices"
    )
    external_id = models.CharField(max_length=150)
    status = models.CharField(max_length=40)
    currency = models.CharField(max_length=3, default="BRL")
    amount_minor = models.PositiveBigIntegerField()
    due_at = models.DateTimeField(null=True, blank=True)
    hosted_url = models.URLField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("tenant", "external_id"), name="unique_tenant_invoice")
        ]


class PaymentAttempt(TenantScopedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payment_attempts")
    external_id = models.CharField(max_length=150)
    status = models.CharField(max_length=40)
    failure_code = models.CharField(max_length=80, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class BillingEvent(UUIDModel):
    provider = models.CharField(max_length=60)
    external_event_id = models.CharField(max_length=180)
    event_type = models.CharField(max_length=100)
    tenant = models.ForeignKey("tenancy.Tenant", null=True, blank=True, on_delete=models.PROTECT)
    payload_digest = models.CharField(max_length=64)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "external_event_id"), name="unique_billing_event"
            )
        ]


class Entitlement(TenantScopedModel):
    key = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    limit = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=40, default="plan")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("tenant", "key"), name="unique_tenant_entitlement")
        ]
