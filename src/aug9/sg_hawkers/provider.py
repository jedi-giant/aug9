from typing import Protocol

from aug9.core.models import Place
from aug9.food_data import load_food_data


class HawkerProvider(Protocol):
    def discover(self, query: str | None = None) -> list[Place]: ...


class FoodCatalogHawkerProvider:
    """Discover hawker centres represented in Aug9's curated food catalog."""

    def discover(self, query: str | None = None) -> list[Place]:
        places: dict[str, Place] = {}
        for item in load_food_data():
            place = Place(**item["place"])
            if place.place_type != "hawker_centre":
                continue
            places.setdefault(place.name.casefold(), place)

        results = list(places.values())
        if not query:
            return results

        normalized = query.casefold().strip()
        matches = [place for place in results if normalized in place.name.casefold()]
        return matches or results
