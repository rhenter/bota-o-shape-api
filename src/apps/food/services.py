from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

ROUNDING = Decimal("0.001")


def food_snapshot(food, grams):
    grams = Decimal(str(grams))
    factor = grams / Decimal("100")
    nutrients = {}
    for value in food.nutrient_values.select_related("nutrient"):
        nutrients[value.nutrient.code] = {
            "name": value.nutrient.name,
            "value": str(
                (value.value_per_100g * factor).quantize(ROUNDING, rounding=ROUND_HALF_UP)
            ),
            "unit": value.nutrient.unit,
            "per_100g": str(value.value_per_100g),
        }
    return {
        "food_id": str(food.id),
        "description": food.name,
        "preparation_state": food.preparation_state,
        "grams": str(grams),
        "source": food.source.kind,
        "source_version": food.source.version,
        "external_id": food.external_id,
        "nutrients": nutrients,
        "estimated": True,
    }


def recipe_snapshot(recipe, portion_grams):
    totals = defaultdict(Decimal)
    details = []
    for ingredient in recipe.ingredients.select_related("food__source").prefetch_related(
        "food__nutrient_values__nutrient"
    ):
        snapshot = food_snapshot(ingredient.food, ingredient.grams)
        details.append(snapshot)
        for code, nutrient in snapshot["nutrients"].items():
            totals[code] += Decimal(nutrient["value"])
    factor = Decimal(str(portion_grams)) / recipe.final_yield_grams
    return {
        "recipe_id": str(recipe.id),
        "portion_grams": str(portion_grams),
        "nutrients": {
            code: str((value * factor).quantize(ROUNDING, rounding=ROUND_HALF_UP))
            for code, value in totals.items()
        },
        "ingredients": details,
        "estimated": True,
    }
