from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/core/", include("apps.core.routes")),
    path("api/user/", include("apps.user.routes")),
]
