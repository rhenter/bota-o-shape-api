from django.contrib import admin

from .admin_utils import TenantScopedAdmin, allowed_tenant_ids
from .models import (
    CoachStudentAssignment,
    ConsentRecord,
    DietitianStudentAssignment,
    GymUnit,
    Invitation,
    Membership,
    ProfessionalCredential,
    RoleAssignment,
    Tenant,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    search_fields = ("name", "legal_name", "cnpj")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        tenant_ids = allowed_tenant_ids(request.user)
        return queryset if tenant_ids is None else queryset.filter(id__in=tenant_ids)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)


for model in (
    GymUnit,
    Membership,
    ProfessionalCredential,
    CoachStudentAssignment,
    DietitianStudentAssignment,
    ConsentRecord,
    Invitation,
):
    admin.site.register(model, TenantScopedAdmin)


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_filter = ("role", "membership__tenant")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        tenant_ids = allowed_tenant_ids(request.user)
        return (
            queryset
            if tenant_ids is None
            else queryset.filter(membership__tenant_id__in=tenant_ids)
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)
