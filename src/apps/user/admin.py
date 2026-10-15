from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.tenancy.admin_utils import allowed_tenant_ids

from .models import User


@admin.register(User)
class BotaOShapeUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        tenant_ids = allowed_tenant_ids(request.user)
        if tenant_ids is None:
            return queryset
        return queryset.filter(memberships__tenant_id__in=tenant_ids).distinct()

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
