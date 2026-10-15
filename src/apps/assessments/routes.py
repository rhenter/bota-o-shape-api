from rest_framework.routers import DefaultRouter

from .views import AssessmentViewSet, ProtocolViewSet

app_name = "assessments"
router = DefaultRouter()
router.register("protocols", ProtocolViewSet, basename="protocol")
router.register("assessments", AssessmentViewSet, basename="assessment")
urlpatterns = router.urls
