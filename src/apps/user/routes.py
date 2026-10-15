from rest_framework.routers import DefaultRouter

from .views import UserViewSet

app_name = "user"

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = router.urls
