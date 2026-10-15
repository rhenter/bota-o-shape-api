from rest_framework.routers import DefaultRouter

from .views import (
    CheckInViewSet,
    HydrationLogViewSet,
    MealLogViewSet,
    MealPlanViewSet,
    NutritionMessageViewSet,
    NutritionProfileViewSet,
)

app_name = "nutrition"
router = DefaultRouter()
router.register("profiles", NutritionProfileViewSet, basename="profile")
router.register("plans", MealPlanViewSet, basename="plan")
router.register("meal-logs", MealLogViewSet, basename="meal-log")
router.register("hydration-logs", HydrationLogViewSet, basename="hydration-log")
router.register("check-ins", CheckInViewSet, basename="check-in")
router.register("messages", NutritionMessageViewSet, basename="message")
urlpatterns = router.urls
