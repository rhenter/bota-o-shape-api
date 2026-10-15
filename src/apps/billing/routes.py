from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BillingPlanViewSet,
    BillingWebhookView,
    EntitlementViewSet,
    InvoiceViewSet,
    SubscriptionViewSet,
)

app_name = "billing"
router = DefaultRouter()
router.register("plans", BillingPlanViewSet)
router.register("subscriptions", SubscriptionViewSet, basename="subscription")
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("entitlements", EntitlementViewSet, basename="entitlement")
urlpatterns = [
    path("webhooks/<str:provider>/", BillingWebhookView.as_view(), name="webhook"),
    *router.urls,
]
