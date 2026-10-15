from django.contrib import admin

from .models import (
    Food,
    FoodImportBatch,
    FoodNutrient,
    FoodSource,
    HouseholdMeasure,
    Nutrient,
    Recipe,
    RecipeIngredient,
)

for model in (
    FoodSource,
    FoodImportBatch,
    Food,
    Nutrient,
    FoodNutrient,
    HouseholdMeasure,
    Recipe,
    RecipeIngredient,
):
    admin.site.register(model)
