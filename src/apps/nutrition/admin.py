from django.contrib import admin

from apps.tenancy.admin_utils import TenantScopedAdmin

from .models import (
    HydrationLog,
    MealLog,
    MealPlan,
    MealPlanCheckIn,
    MealPlanVersion,
    MealSlot,
    NutritionAssessment,
    NutritionMessage,
    NutritionProfile,
    PlannedFood,
    SubstitutionOption,
)

for model in (
    NutritionProfile,
    NutritionAssessment,
    MealPlan,
    MealPlanVersion,
    MealSlot,
    PlannedFood,
    SubstitutionOption,
    MealLog,
    HydrationLog,
    MealPlanCheckIn,
    NutritionMessage,
):
    admin.site.register(model, TenantScopedAdmin)
