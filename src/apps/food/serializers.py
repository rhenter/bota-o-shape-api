from rest_framework import serializers

from .models import Food, FoodSource, HouseholdMeasure, Recipe, RecipeIngredient


class FoodSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodSource
        fields = "__all__"


class HouseholdMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseholdMeasure
        fields = ("id", "name", "grams", "evidence")


class FoodSerializer(serializers.ModelSerializer):
    source = FoodSourceSerializer(read_only=True)
    household_measures = HouseholdMeasureSerializer(many=True, read_only=True)

    class Meta:
        model = Food
        exclude = ("raw_payload",)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeIngredient
        exclude = ("recipe",)


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(many=True)

    class Meta:
        model = Recipe
        fields = "__all__"

    def create(self, validated_data):
        ingredients = validated_data.pop("ingredients")
        recipe = Recipe.objects.create(**validated_data)
        RecipeIngredient.objects.bulk_create(
            [RecipeIngredient(recipe=recipe, **ingredient) for ingredient in ingredients]
        )
        return recipe
