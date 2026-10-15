from django.contrib import admin

from .models import Membership


def allowed_tenant_ids(user):
    if user.is_superuser:
        return None
    return Membership.objects.filter(user=user, status=Membership.Status.ACTIVE).values_list(
        "tenant_id", flat=True
    )


class TenantScopedAdmin(admin.ModelAdmin):
    list_filter = ("tenant",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        tenant_ids = allowed_tenant_ids(request.user)
        return queryset if tenant_ids is None else queryset.filter(tenant_id__in=tenant_ids)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._allowed(request, obj)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def _allowed(self, request, obj):
        if obj is None or request.user.is_superuser:
            return True
        return Membership.objects.filter(
            user=request.user,
            tenant_id=obj.tenant_id,
            status=Membership.Status.ACTIVE,
        ).exists()
