from decimal import Decimal, InvalidOperation

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .integrations import USDAFoodDataCentralClient
from .models import Food, Recipe
from .serializers import FoodSerializer, RecipeSerializer
from .services import food_snapshot, recipe_snapshot


class FoodViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = (
        Food.objects.filter(source__is_active=True)
        .select_related("source")
        .prefetch_related("household_measures")
    )
    serializer_class = FoodSerializer
    filterset_fields = ("source__kind", "preparation_state", "branded", "reviewed")
    search_fields = ("name", "preparation_state")

    @action(detail=False, methods=["get"], url_path="external/usda")
    def external_usda(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response({"detail": "Informe ao menos dois caracteres."}, status=400)
        return Response(
            USDAFoodDataCentralClient().search(query, request.query_params.get("page_size", 20))
        )

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        food = self.get_object()
        grams = request.data.get("grams")
        measure_id = request.data.get("measure_id")
        if measure_id:
            measure = food.household_measures.filter(pk=measure_id).first()
            if not measure:
                return Response(
                    {"detail": "Medida não documentada para este alimento."}, status=400
                )
            grams = measure.grams
        try:
            grams = Decimal(str(grams))
            if grams <= 0:
                raise InvalidOperation
        except InvalidOperation, TypeError:
            return Response({"detail": "Informe uma quantidade positiva em gramas."}, status=400)
        return Response(food_snapshot(food, grams))


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.prefetch_related("ingredients__food__nutrient_values__nutrient")
    serializer_class = RecipeSerializer

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        try:
            portion = Decimal(str(request.data.get("grams")))
            if portion <= 0:
                raise InvalidOperation
        except InvalidOperation, TypeError:
            return Response({"detail": "Informe uma porção positiva em gramas."}, status=400)
        return Response(recipe_snapshot(self.get_object(), portion))
