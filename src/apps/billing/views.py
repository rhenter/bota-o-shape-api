import hashlib

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.models import AuditEvent
from apps.tenancy.models import RoleAssignment, Tenant
from apps.tenancy.services import get_membership, require_roles

from .models import AcademySubscription, BillingEvent, BillingPlan, Entitlement, Invoice
from .serializers import (
    BillingPlanSerializer,
    EntitlementSerializer,
    InvoiceSerializer,
    SubscriptionSerializer,
)
from .services import get_provider


class BillingPlanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = BillingPlan.objects.filter(is_active=True)
    serializer_class = BillingPlanSerializer
    permission_classes = [AllowAny]


class SubscriptionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = SubscriptionSerializer
    queryset = AcademySubscription.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = require_roles(self.request, RoleAssignment.Role.BILLING_MANAGE)
        return AcademySubscription.objects.filter(tenant=membership.tenant).select_related("plan")

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        subscription = self.get_object()
        data = get_provider().create_checkout(subscription, request.data.get("return_url"))
        return Response(data)

    @action(detail=True, methods=["post"])
    def portal(self, request, pk=None):
        subscription = self.get_object()
        data = get_provider().create_portal(subscription, request.data.get("return_url"))
        return Response(data)


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = require_roles(self.request, RoleAssignment.Role.BILLING_MANAGE)
        return Invoice.objects.filter(tenant=membership.tenant)


class EntitlementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = EntitlementSerializer
    queryset = Entitlement.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        membership = get_membership(self.request)
        return Entitlement.objects.filter(tenant=membership.tenant, enabled=True)


class BillingWebhookSerializer(serializers.Serializer):
    pass


class BillingWebhookView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = BillingWebhookSerializer

    @transaction.atomic
    def post(self, request, provider):
        parsed = get_provider().parse_webhook(
            request.body, request.headers.get("X-Billing-Signature", "")
        )
        event_id = parsed["id"]
        existing = BillingEvent.objects.filter(
            provider=provider, external_event_id=event_id
        ).first()
        if existing:
            return Response(status=status.HTTP_200_OK)
        tenant = Tenant.objects.filter(pk=parsed.get("tenant_id")).first()
        event = BillingEvent.objects.create(
            provider=provider,
            external_event_id=event_id,
            event_type=parsed["type"],
            tenant=tenant,
            payload_digest=hashlib.sha256(request.body).hexdigest(),
            processed_at=timezone.now(),
        )
        AuditEvent.objects.create(
            tenant=tenant,
            action="billing.webhook_processed",
            target_id=str(event.id),
            metadata={"type": event.event_type},
        )
        return Response(status=status.HTTP_200_OK)
