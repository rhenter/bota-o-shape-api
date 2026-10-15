import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache
from rest_framework.exceptions import APIException


class FoodSourceUnavailable(APIException):
    status_code = 503
    default_detail = "A fonte externa de alimentos está indisponível."


class USDAFoodDataCentralClient:
    base_url = "https://api.nal.usda.gov/fdc/v1"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("USDA_API_KEY")

    def search(self, query, page_size=20):
        if not self.api_key:
            raise FoodSourceUnavailable("USDA_API_KEY não configurada no backend.")
        page_size = min(max(int(page_size), 1), 50)
        cache_key = f"usda:search:{query.strip().lower()}:{page_size}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        params = urlencode({"api_key": self.api_key, "query": query, "pageSize": page_size})
        try:
            with urlopen(f"{self.base_url}/foods/search?{params}", timeout=8) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise FoodSourceUnavailable() from exc
        foods = [
            {
                "external_id": str(item["fdcId"]),
                "description": item.get("description", ""),
                "data_type": item.get("dataType", ""),
                "brand": item.get("brandOwner", ""),
                "source": "usda",
            }
            for item in payload.get("foods", [])
        ]
        cache.set(cache_key, foods, timeout=3600)
        return foods
