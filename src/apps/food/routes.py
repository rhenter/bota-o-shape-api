from rest_framework.routers import DefaultRouter

from .views import FoodViewSet, RecipeViewSet

app_name = "food"
router = DefaultRouter()
router.register("foods", FoodViewSet)
router.register("recipes", RecipeViewSet)
urlpatterns = router.urls
