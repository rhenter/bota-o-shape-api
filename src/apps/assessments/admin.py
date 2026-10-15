from django.contrib import admin

from apps.tenancy.admin_utils import TenantScopedAdmin

from .models import Assessment, AssessmentReport, Measurement, MeasurementProtocol

for model in (MeasurementProtocol, Assessment, Measurement, AssessmentReport):
    admin.site.register(model, TenantScopedAdmin)
