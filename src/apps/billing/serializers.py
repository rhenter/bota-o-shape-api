from rest_framework import serializers

from .models import (
    AcademySubscription,
    BillingEvent,
    BillingPlan,
    Entitlement,
    Invoice,
    PaymentAttempt,
)


class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = "__all__"


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = BillingPlanSerializer(source="plan", read_only=True)

    class Meta:
        model = AcademySubscription
        exclude = ("tenant", "external_customer_id", "external_subscription_id")
        read_only_fields = (
            "status",
            "provider",
            "current_period_start",
            "current_period_end",
            "grace_ends_at",
        )


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        exclude = ("tenant",)


class PaymentAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAttempt
        exclude = ("tenant", "external_id", "failure_code")


class BillingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingEvent
        exclude = ("payload_digest", "processing_error")


class EntitlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entitlement
        exclude = ("tenant",)
