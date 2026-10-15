from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.assessments.models import Assessment, Measurement, MeasurementProtocol
from apps.assessments.services import build_comparisons
from apps.food.models import Food, FoodNutrient, FoodSource, Nutrient, Recipe, RecipeIngredient
from apps.food.services import food_snapshot, recipe_snapshot
from apps.tenancy.models import ConsentRecord


@pytest.mark.django_db
def test_assessment_compares_only_compatible_measurements(tenant, coach_member, student_member):
    coach, _ = coach_member
    student, _ = student_member
    consent = ConsentRecord.objects.create(
        tenant=tenant, subject=student, purpose="physical_assessment"
    )
    protocol = MeasurementProtocol.objects.create(
        tenant=tenant, name="Perímetros", version="1", method="circumference", sites=["waist"]
    )
    previous = Assessment.objects.create(
        tenant=tenant,
        student=student,
        evaluator=coach,
        assessed_at=timezone.now() - timedelta(days=30),
        status=Assessment.Status.COMPLETED,
        consent=consent,
    )
    Measurement.objects.create(
        tenant=tenant,
        assessment=previous,
        metric="waist",
        raw_value=Decimal("90"),
        unit="cm",
        anatomical_site="umbilicus",
        method="circumference",
        protocol=protocol,
    )
    current = Assessment.objects.create(
        tenant=tenant, student=student, evaluator=coach, assessed_at=timezone.now(), consent=consent
    )
    compatible = Measurement.objects.create(
        tenant=tenant,
        assessment=current,
        metric="waist",
        raw_value=Decimal("87"),
        unit="cm",
        anatomical_site="umbilicus",
        method="circumference",
        protocol=protocol,
    )
    incompatible = Measurement.objects.create(
        tenant=tenant,
        assessment=current,
        metric="waist",
        raw_value=Decimal("34"),
        unit="in",
        anatomical_site="umbilicus",
        method="circumference",
        protocol=protocol,
    )
    result = {item["measurement_id"]: item for item in build_comparisons(current)}
    assert result[str(compatible.id)]["comparison_status"] == "decreased"
    assert result[str(compatible.id)]["difference"] == "-3.0000"
    assert result[str(incompatible.id)]["comparison_status"] == "not_comparable"


@pytest.mark.django_db
def test_food_and_recipe_calculation_preserve_missing_nutrients():
    source = FoodSource.objects.create(name="TBCA", kind="tbca", version="2026")
    energy = Nutrient.objects.create(code="energy_kcal", name="Energia", unit="kcal")
    food = Food.objects.create(
        source=source, external_id="1", name="Arroz", preparation_state="cozido"
    )
    FoodNutrient.objects.create(food=food, nutrient=energy, value_per_100g=Decimal("128"))
    snapshot = food_snapshot(food, Decimal("150"))
    assert snapshot["nutrients"]["energy_kcal"]["value"] == "192.000"
    assert "protein_g" not in snapshot["nutrients"]
    recipe = Recipe.objects.create(name="Arroz porcionado", final_yield_grams=Decimal("300"))
    RecipeIngredient.objects.create(recipe=recipe, food=food, grams=Decimal("300"))
    calculated = recipe_snapshot(recipe, Decimal("100"))
    assert calculated["nutrients"]["energy_kcal"] == "128.000"
