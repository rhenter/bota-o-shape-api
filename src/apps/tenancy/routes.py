from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CoachStudentAssignmentViewSet,
    ConsentRecordViewSet,
    DietitianStudentAssignmentViewSet,
    GymUnitViewSet,
    InvitationAcceptView,
    MembershipViewSet,
    OwnerRegistrationView,
    ProfessionalCredentialViewSet,
    TenantViewSet,
)

app_name = "tenancy"
router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("units", GymUnitViewSet, basename="unit")
router.register("memberships", MembershipViewSet, basename="membership")
router.register("credentials", ProfessionalCredentialViewSet, basename="credential")
router.register("coach-assignments", CoachStudentAssignmentViewSet, basename="coach-assignment")
router.register(
    "dietitian-assignments", DietitianStudentAssignmentViewSet, basename="dietitian-assignment"
)
router.register("consents", ConsentRecordViewSet, basename="consent")

urlpatterns = [
    path("owner/register/", OwnerRegistrationView.as_view(), name="owner-register"),
    path("invitations/accept/", InvitationAcceptView.as_view(), name="invitation-accept"),
    path("", include(router.urls)),
]
