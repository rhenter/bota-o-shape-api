from django.contrib import admin

from apps.tenancy.admin_utils import TenantScopedAdmin

from .models import AuditEvent, DataSubjectRequest

admin.site.register(AuditEvent, TenantScopedAdmin)
admin.site.register(DataSubjectRequest, TenantScopedAdmin)
