from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import AcademySubscription, Entitlement

READ_ONLY_STATUSES = {
    AcademySubscription.Status.DELINQUENT,
    AcademySubscription.Status.CANCELLED,
    AcademySubscription.Status.SUSPENDED,
}


def get_subscription(tenant):
    return (
        AcademySubscription.objects.filter(tenant=tenant)
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def require_commercial_write(tenant, feature=None):
    subscription = get_subscription(tenant)
    if not subscription:
        raise PermissionDenied("A academia não possui assinatura ou piloto ativo.")
    if subscription.status in READ_ONLY_STATUSES:
        if not subscription.grace_ends_at or subscription.grace_ends_at <= timezone.now():
            raise PermissionDenied("A academia está em modo somente leitura.")
    if feature:
        entitlement = Entitlement.objects.filter(tenant=tenant, key=feature, enabled=True).first()
        plan_has_feature = feature in subscription.plan.features
        if not entitlement and not plan_has_feature:
            raise PermissionDenied("Recurso não incluído no contrato da academia.")
    return subscription


def enforce_limit(tenant, key, current_count):
    subscription = require_commercial_write(tenant)
    entitlement = Entitlement.objects.filter(tenant=tenant, key=key, enabled=True).first()
    limit = entitlement.limit if entitlement else subscription.plan.limits.get(key)
    if limit is not None and current_count >= int(limit):
        raise ValidationError(f"Limite contratado atingido para {key}.")


class BillingProvider:
    def create_checkout(self, subscription, return_url):
        raise NotImplementedError

    def create_portal(self, subscription, return_url):
        raise NotImplementedError

    def parse_webhook(self, body, signature):
        raise NotImplementedError


class UnconfiguredBillingProvider(BillingProvider):
    def create_checkout(self, subscription, return_url):
        raise ValidationError("Provedor de cobrança ainda não configurado.")

    create_portal = create_checkout

    def parse_webhook(self, body, signature):
        raise PermissionDenied("Provedor de cobrança ainda não configurado.")


def get_provider():
    return UnconfiguredBillingProvider()
