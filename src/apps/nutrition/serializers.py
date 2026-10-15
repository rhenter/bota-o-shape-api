from django.db import transaction
from rest_framework import serializers

from apps.food.services import food_snapshot

from .models import (
    HydrationLog,
    MealLog,
    MealPlan,
    MealPlanCheckIn,
    MealPlanVersion,
    MealSlot,
    NutritionMessage,
    NutritionProfile,
    PlannedFood,
    SubstitutionOption,
)


class SubstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubstitutionOption
        exclude = ("tenant", "planned_food", "nutrition_snapshot")


class PlannedFoodSerializer(serializers.ModelSerializer):
    substitutions = SubstitutionSerializer(many=True, required=False)

    class Meta:
        model = PlannedFood
        exclude = ("tenant", "meal_slot", "nutrition_snapshot")

    def validate(self, attrs):
        if attrs.get("food") and not attrs.get("grams"):
            raise serializers.ValidationError(
                {"grams": "Alimento catalogado exige quantidade em gramas."}
            )
        return attrs


class MealSlotSerializer(serializers.ModelSerializer):
    foods = PlannedFoodSerializer(many=True)

    class Meta:
        model = MealSlot
        exclude = ("tenant", "version")


class MealPlanVersionSerializer(serializers.ModelSerializer):
    meal_slots = MealSlotSerializer(many=True)

    class Meta:
        model = MealPlanVersion
        exclude = ("tenant", "plan", "author")
        read_only_fields = ("version", "crn", "crn_state", "published_at")


class MealPlanSerializer(serializers.ModelSerializer):
    versions = MealPlanVersionSerializer(many=True, read_only=True)
    draft = MealPlanVersionSerializer(write_only=True)

    class Meta:
        model = MealPlan
        exclude = ("tenant", "author", "active_version")
        read_only_fields = ("status",)

    @transaction.atomic
    def create(self, validated_data):
        draft = validated_data.pop("draft")
        slots = draft.pop("meal_slots")
        credential = self.context["credential"]
        plan = MealPlan.objects.create(**validated_data)
        version = MealPlanVersion.objects.create(
            tenant=plan.tenant,
            plan=plan,
            author=plan.author,
            version=1,
            crn=credential.registration_number,
            crn_state=credential.state,
            **draft,
        )
        create_slots(version, slots)
        return plan


class StudentMealPlanSerializer(serializers.ModelSerializer):
    active_version = MealPlanVersionSerializer(read_only=True)

    class Meta:
        model = MealPlan
        fields = (
            "id",
            "objective",
            "starts_on",
            "ends_on",
            "review_on",
            "status",
            "active_version",
        )


def create_slots(version, slots):
    for slot_data in slots:
        foods = slot_data.pop("foods")
        slot = MealSlot.objects.create(tenant=version.tenant, version=version, **slot_data)
        for food_data in foods:
            substitutions = food_data.pop("substitutions", [])
            catalog_food = food_data.get("food")
            snapshot = food_snapshot(catalog_food, food_data["grams"]) if catalog_food else {}
            planned = PlannedFood.objects.create(
                tenant=version.tenant, meal_slot=slot, nutrition_snapshot=snapshot, **food_data
            )
            for substitution in substitutions:
                catalog_substitute = substitution.get("food")
                sub_snapshot = (
                    food_snapshot(catalog_substitute, substitution["grams"])
                    if catalog_substitute and substitution.get("grams")
                    else {}
                )
                SubstitutionOption.objects.create(
                    tenant=version.tenant,
                    planned_food=planned,
                    nutrition_snapshot=sub_snapshot,
                    **substitution,
                )


class NutritionProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionProfile
        exclude = ("tenant",)


class MealLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealLog
        exclude = ("tenant", "student", "nutrition_snapshot")


class HydrationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HydrationLog
        exclude = ("tenant", "student")


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealPlanCheckIn
        exclude = ("tenant", "student")


class NutritionMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionMessage
        exclude = ("tenant", "author")
