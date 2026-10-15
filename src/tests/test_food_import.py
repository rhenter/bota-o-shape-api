from io import StringIO

import pytest
from django.core.management import call_command

from apps.food.models import Food, FoodImportBatch, FoodNutrient, FoodSource, Nutrient


@pytest.mark.django_db
def test_import_food_table_is_idempotent_and_preserves_missing_values(tmp_path):
    csv_file = tmp_path / "tbca-7.3.csv"
    csv_file.write_text(
        "external_id;name;preparation_state;nutrient_code;nutrient_name;nutrient_unit;"
        "value_per_100g;data_type\n"
        "BRC0018A;Arroz polido;cozido;energy_kcal;Energia;kcal;128,0;Calculado\n"
        "BRC0018A;Arroz polido;cozido;protein_g;Proteína;g;2,5;Analítico\n"
        "BRC0018A;Arroz polido;cozido;fiber_g;Fibra;g;NA;Analítico\n",
        encoding="utf-8",
    )

    output = StringIO()
    command_options = {
        "source": "tbca",
        "source_version": "7.3",
        "license_status": "approved",
        "activate": True,
        "stdout": output,
    }
    call_command("import_food_table", csv_file, **command_options)
    call_command("import_food_table", csv_file, **command_options)

    source = FoodSource.objects.get(kind="tbca", version="7.3")
    food = Food.objects.get(source=source, external_id="BRC0018A")
    assert source.is_active is True
    assert FoodImportBatch.objects.get(source=source).status == "completed"
    assert Nutrient.objects.count() == 3
    assert FoodNutrient.objects.filter(food=food).count() == 2
    assert food.nutrient_values.get(nutrient__code="protein_g").value_per_100g == 2.5
    assert "Importação concluída: 1 alimentos" in output.getvalue()


@pytest.mark.django_db
def test_import_food_table_supports_quotes_after_dialect_sample(tmp_path):
    csv_file = tmp_path / "quoted.csv"
    padding = "".join(
        f"{index},Padding {index},energy_kcal,Energia,kcal,100\n" for index in range(100)
    )
    csv_file.write_text(
        "external_id,name,nutrient_code,nutrient_name,nutrient_unit,value_per_100g\n"
        f"{padding}"
        'quoted,"Bebida, café, ""média""",energy_kcal,Energia,kcal,35\n',
        encoding="utf-8",
    )

    call_command(
        "import_food_table",
        csv_file,
        source="tbca",
        source_version="7.3",
    )

    assert Food.objects.get(external_id="quoted").name == 'Bebida, café, "média"'
