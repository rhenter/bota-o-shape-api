from rest_framework.routers import DefaultRouter

from .views import (
    EquipmentViewSet,
    ExerciseViewSet,
    MuscleGroupViewSet,
    WorkoutAssignmentViewSet,
    WorkoutSessionViewSet,
    WorkoutTemplateViewSet,
)

app_name = "workouts"
router = DefaultRouter()
router.register("equipment", EquipmentViewSet)
router.register("muscle-groups", MuscleGroupViewSet)
router.register("exercises", ExerciseViewSet)
router.register("templates", WorkoutTemplateViewSet)
router.register("assignments", WorkoutAssignmentViewSet)
router.register("sessions", WorkoutSessionViewSet, basename="session")
urlpatterns = router.urls
