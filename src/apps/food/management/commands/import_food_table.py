import csv
import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.food.models import Food, FoodImportBatch, FoodNutrient, FoodSource, Nutrient

REQUIRED_COLUMNS = {
    "external_id",
    "name",
    "nutrient_code",
    "nutrient_name",
    "nutrient_unit",
    "value_per_100g",
}
MISSING_VALUES = {"", "-", "na", "n/a", "nd", "tr"}


class Command(BaseCommand):
    help = "Importa uma tabela de composição alimentar normalizada em CSV."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument(
            "--source", required=True, choices=[choice for choice, _ in FoodSource.Kind.choices]
        )
        parser.add_argument("--source-version", required=True)
        parser.add_argument("--source-name")
        parser.add_argument("--batch-id")
        parser.add_argument("--attribution-url", default="")
        parser.add_argument("--license-status", default="pending_review")
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Disponibiliza a fonte no catálogo. Use apenas após aprovar a licença e os dados.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        if not file_path.is_file():
            raise CommandError(f"Arquivo não encontrado: {file_path}")

        checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
        rows = self._read_rows(file_path)
        source_name = options["source_name"] or dict(FoodSource.Kind.choices)[options["source"]]
        source, _ = FoodSource.objects.update_or_create(
            kind=options["source"],
            version=options["source_version"],
            defaults={
                "name": source_name,
                "attribution_url": options["attribution_url"],
                "license_status": options["license_status"],
                "is_active": options["activate"],
            },
        )
        batch_id = options["batch_id"] or file_path.name
        batch, _ = FoodImportBatch.objects.update_or_create(
            source=source,
            external_batch_id=batch_id,
            defaults={"checksum": checksum, "status": "pending", "error_summary": ""},
        )

        try:
            with transaction.atomic():
                imported_count = self._import_rows(source, rows)
                batch.status = "completed"
                batch.imported_count = imported_count
                batch.error_summary = ""
                batch.save(update_fields=("status", "imported_count", "error_summary"))
        except Exception as exc:
            batch.status = "failed"
            batch.error_summary = str(exc)
            batch.save(update_fields=("status", "error_summary"))
            raise CommandError(f"Falha ao importar {file_path}: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída: {imported_count} alimentos, fonte {source.kind} "
                f"{source.version}, lote {batch.external_batch_id}."
            )
        )

    def _read_rows(self, file_path):
        try:
            with file_path.open(encoding="utf-8-sig", newline="") as stream:
                sample = stream.read(4096)
                stream.seek(0)
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;").delimiter
                reader = csv.DictReader(stream, delimiter=delimiter)
                missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or ())
                if missing_columns:
                    missing = ", ".join(sorted(missing_columns))
                    raise CommandError(f"Colunas obrigatórias ausentes: {missing}")
                return [self._normalize_row(row, line) for line, row in enumerate(reader, 2)]
        except UnicodeDecodeError as exc:
            raise CommandError("O arquivo deve estar em UTF-8.") from exc
        except csv.Error as exc:
            raise CommandError(f"CSV inválido: {exc}") from exc

    def _normalize_row(self, row, line):
        normalized = {key: (value or "").strip() for key, value in row.items() if key}
        for column in ("external_id", "name", "nutrient_code", "nutrient_name", "nutrient_unit"):
            if not normalized[column]:
                raise CommandError(f"Linha {line}: {column} não pode ficar vazio.")

        raw_value = normalized["value_per_100g"].lower()
        value = None
        if raw_value not in MISSING_VALUES:
            try:
                value = Decimal(raw_value.replace(" ", "").replace(",", "."))
            except InvalidOperation as exc:
                raise CommandError(
                    f"Linha {line}: value_per_100g inválido: {normalized['value_per_100g']}"
                ) from exc
        normalized["value_per_100g"] = value
        normalized["branded"] = normalized.get("branded", "").lower() in {
            "1",
            "true",
            "sim",
            "yes",
        }
        return normalized

    def _import_rows(self, source, rows):
        foods = {}
        nutrients = {}
        nutrient_definitions = {}

        for row in rows:
            external_id = row["external_id"]
            food = foods.get(external_id)
            if food is None:
                food, _ = Food.objects.update_or_create(
                    source=source,
                    external_id=external_id,
                    defaults={
                        "name": row["name"],
                        "preparation_state": row.get("preparation_state", ""),
                        "edible_description": row.get("edible_description", ""),
                        "branded": row["branded"],
                        "reviewed": False,
                    },
                )
                foods[external_id] = food

            nutrient_code = row["nutrient_code"]
            definition = (row["nutrient_name"], row["nutrient_unit"])
            previous_definition = nutrient_definitions.setdefault(nutrient_code, definition)
            if previous_definition != definition:
                raise ValueError(
                    f"Nutriente {nutrient_code} possui nomes ou unidades conflitantes no arquivo."
                )

            nutrient = nutrients.get(nutrient_code)
            if nutrient is None:
                nutrient, created = Nutrient.objects.get_or_create(
                    code=nutrient_code,
                    defaults={"name": row["nutrient_name"], "unit": row["nutrient_unit"]},
                )
                if not created and (nutrient.name, nutrient.unit) != definition:
                    raise ValueError(
                        f"Nutriente {nutrient_code} conflita com a definição já cadastrada."
                    )
                nutrients[nutrient_code] = nutrient

            if row["value_per_100g"] is not None:
                FoodNutrient.objects.update_or_create(
                    food=food,
                    nutrient=nutrient,
                    defaults={
                        "value_per_100g": row["value_per_100g"],
                        "data_type": row.get("data_type", ""),
                    },
                )

        return len(foods)
