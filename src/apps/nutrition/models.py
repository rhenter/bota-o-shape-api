from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel
from apps.food.models import Food


class NutritionProfile(TenantScopedModel):
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="nutrition_profile"
    )
    habits = models.JSONField(default=dict, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    restrictions = models.JSONField(default=list, blank=True)
    preferences = models.JSONField(default=list, blank=True)


class NutritionAssessment(TenantScopedModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    dietitian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="nutrition_assessments"
    )
    data = models.JSONField(default=dict)
    assessed_at = models.DateTimeField()


class MealPlan(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        PAUSED = "paused", "Paused"
        SUPERSEDED = "superseded", "Superseded"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="meal_plans"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="meal_plans_authored"
    )
    objective = models.TextField(blank=True)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    review_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    active_version = models.ForeignKey(
        "MealPlanVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="active_for_plans",
    )


class MealPlanVersion(TenantScopedModel):
    plan = models.ForeignKey(MealPlan, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    crn = models.CharField(max_length=50)
    crn_state = models.CharField(max_length=2)
    change_reason = models.TextField(blank=True)
    hydration_guidance = models.TextField(blank=True)
    complementary_guidance = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plan", "version"), name="unique_meal_plan_version")
        ]


class MealSlot(TenantScopedModel):
    version = models.ForeignKey(
        MealPlanVersion, on_delete=models.CASCADE, related_name="meal_slots"
    )
    day = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=120)
    scheduled_time = models.TimeField(null=True, blank=True)
    order = models.PositiveIntegerField()
    instructions = models.TextField(blank=True)

    class Meta:
        ordering = ("day", "order")


class PlannedFood(TenantScopedModel):
    meal_slot = models.ForeignKey(MealSlot, on_delete=models.CASCADE, related_name="foods")
    food = models.ForeignKey(Food, null=True, blank=True, on_delete=models.PROTECT)
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    grams = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    preparation = models.TextField(blank=True)
    observation = models.TextField(blank=True)
    nutrition_snapshot = models.JSONField(default=dict, blank=True)


class SubstitutionOption(TenantScopedModel):
    planned_food = models.ForeignKey(
        PlannedFood, on_delete=models.CASCADE, related_name="substitutions"
    )
    food = models.ForeignKey(Food, null=True, blank=True, on_delete=models.PROTECT)
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    grams = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    nutrition_snapshot = models.JSONField(default=dict, blank=True)


class MealLog(TenantScopedModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    logged_at = models.DateTimeField()
    description = models.TextField()
    food = models.ForeignKey(Food, null=True, blank=True, on_delete=models.PROTECT)
    grams = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    nutrition_snapshot = models.JSONField(default=dict, blank=True)


class HydrationLog(TenantScopedModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    logged_at = models.DateTimeField()
    milliliters = models.PositiveIntegerField()


class MealPlanCheckIn(TenantScopedModel):
    class Adherence(models.TextChoices):
        FOLLOWED = "followed", "Followed"
        PARTIAL = "partial", "Partially followed"
        NOT_FOLLOWED = "not_followed", "Not followed"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    version = models.ForeignKey(MealPlanVersion, on_delete=models.PROTECT, related_name="check_ins")
    meal_slot = models.ForeignKey(MealSlot, null=True, blank=True, on_delete=models.PROTECT)
    adherence = models.CharField(max_length=16, choices=Adherence.choices)
    note = models.TextField(blank=True)
    question = models.TextField(blank=True)
    checked_at = models.DateTimeField()


class NutritionMessage(TenantScopedModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="nutrition_messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="nutrition_messages_authored",
    )
    body = models.TextField()
    shared_with_coach = models.BooleanField(default=False)
