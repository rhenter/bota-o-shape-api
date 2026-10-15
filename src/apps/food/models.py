from django.db import models

from apps.core.models import UUIDModel


class FoodSource(UUIDModel):
    class Kind(models.TextChoices):
        TBCA = "tbca", "TBCA"
        USDA = "usda", "USDA FoodData Central"
        INTERNAL = "internal", "Internal reviewed data"

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    version = models.CharField(max_length=80)
    attribution_url = models.URLField(blank=True)
    license_status = models.CharField(max_length=80, default="pending_review")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("kind", "version"), name="unique_food_source_version")
        ]


class FoodImportBatch(UUIDModel):
    source = models.ForeignKey(FoodSource, on_delete=models.PROTECT, related_name="batches")
    external_batch_id = models.CharField(max_length=120)
    checksum = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=30, default="pending")
    imported_count = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("source", "external_batch_id"), name="unique_food_import_batch"
            )
        ]


class Food(UUIDModel):
    source = models.ForeignKey(FoodSource, on_delete=models.PROTECT, related_name="foods")
    external_id = models.CharField(max_length=120)
    name = models.CharField(max_length=240)
    preparation_state = models.CharField(max_length=120, blank=True)
    edible_description = models.CharField(max_length=160, blank=True)
    branded = models.BooleanField(default=False)
    raw_payload = models.JSONField(default=dict, blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("source", "external_id"), name="unique_external_food")
        ]
        indexes = [models.Index(fields=("name", "preparation_state"))]


class Nutrient(UUIDModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=24)


class FoodNutrient(UUIDModel):
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="nutrient_values")
    nutrient = models.ForeignKey(Nutrient, on_delete=models.PROTECT)
    value_per_100g = models.DecimalField(max_digits=14, decimal_places=6)
    data_type = models.CharField(max_length=60, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("food", "nutrient"), name="unique_food_nutrient")
        ]


class HouseholdMeasure(UUIDModel):
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="household_measures")
    name = models.CharField(max_length=100)
    grams = models.DecimalField(max_digits=10, decimal_places=3)
    evidence = models.CharField(max_length=240)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("food", "name"), name="unique_food_measure")]


class Recipe(UUIDModel):
    name = models.CharField(max_length=200)
    final_yield_grams = models.DecimalField(max_digits=12, decimal_places=3)
    notes = models.TextField(blank=True)


class RecipeIngredient(UUIDModel):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    food = models.ForeignKey(Food, on_delete=models.PROTECT)
    grams = models.DecimalField(max_digits=12, decimal_places=3)
    is_added_fat_sugar_or_salt = models.BooleanField(default=False)
