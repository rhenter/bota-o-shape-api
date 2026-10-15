from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/core/", include("apps.core.routes")),
    path("api/user/", include("apps.user.routes")),
    path("api/tenancy/", include("apps.tenancy.routes")),
    path("api/workouts/", include("apps.workouts.routes")),
    path("api/assessments/", include("apps.assessments.routes")),
    path("api/food/", include("apps.food.routes")),
    path("api/nutrition/", include("apps.nutrition.routes")),
    path("api/billing/", include("apps.billing.routes")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
