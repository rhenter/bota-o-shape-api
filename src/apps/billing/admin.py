from django.contrib import admin

from apps.tenancy.admin_utils import TenantScopedAdmin

from .models import (
    AcademySubscription,
    BillingEvent,
    BillingPlan,
    Entitlement,
    Invoice,
    PaymentAttempt,
)

admin.site.register(BillingPlan)
admin.site.register(BillingEvent)
for model in (AcademySubscription, Invoice, PaymentAttempt, Entitlement):
    admin.site.register(model, TenantScopedAdmin)
