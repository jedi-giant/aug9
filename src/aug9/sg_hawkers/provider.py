import math
import sqlite3
from typing import Protocol

import psycopg

from aug9.core.models import Place
from aug9.discovery.models import EntityType
from aug9.discovery.models import FoodListing
from aug9.discovery.repository import DiscoveryRepository
from aug9.food_data import load_hawker_data


class HawkerProvider(Protocol):
    def discover(self, query: str | None = None) -> list[Place]: ...

    def discover_near(self, latitude: float, longitude: float) -> list[Place]: ...

    def food_listings(self) -> list[FoodListing]: ...


def distance_km(origin_latitude: float, origin_longitude: float, place: Place) -> float:
    if place.latitude is None or place.longitude is None:
        return math.inf
    phi1 = math.radians(origin_latitude)
    phi2 = math.radians(place.latitude)
    delta_phi = math.radians(place.latitude - origin_latitude)
    delta_lambda = math.radians(place.longitude - origin_longitude)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 6371 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class CuratedHawkerProvider:
    """Discover hawker centres represented in Aug9's curated location catalog."""

    def discover(self, query: str | None = None) -> list[Place]:
        results = [Place(**item) for item in load_hawker_data()]
        if not query:
            return results

        normalized = query.casefold().strip()
        matches = [place for place in results if normalized in place.name.casefold()]
        return matches or results

    def discover_near(self, latitude: float, longitude: float) -> list[Place]:
        return sorted(
            self.discover(),
            key=lambda place: distance_km(latitude, longitude, place),
        )[:5]

    def food_listings(self) -> list[FoodListing]:
        return []


class DatabaseHawkerProvider:
    """Read canonical hawker records and retain the curated catalog as fallback."""

    def __init__(
        self,
        repository: DiscoveryRepository | None = None,
        fallback: HawkerProvider | None = None,
        *,
        limit: int = 12,
    ) -> None:
        self.repository = repository or DiscoveryRepository()
        self.fallback = fallback or CuratedHawkerProvider()
        self.limit = limit

    def discover(self, query: str | None = None) -> list[Place]:
        try:
            entities = self.repository.search_entities(
                query,
                entity_type=EntityType.HAWKER_CENTRE.value,
                limit=self.limit,
            )
        except (psycopg.Error, sqlite3.Error):
            return self.fallback.discover(query)

        if not entities:
            if query:
                try:
                    canonical_records = self.repository.search_entities(
                        None,
                        entity_type=EntityType.HAWKER_CENTRE.value,
                        limit=1,
                    )
                except (psycopg.Error, sqlite3.Error):
                    return self.fallback.discover(query)
                if canonical_records:
                    return []
            return self.fallback.discover(query)

        return [
            Place(
                name=entity.name,
                place_type=entity.entity_type.value,
                address=entity.address,
                postal_code=entity.postal_code,
                latitude=entity.latitude,
                longitude=entity.longitude,
            )
            for entity in entities
        ]

    def discover_near(self, latitude: float, longitude: float) -> list[Place]:
        try:
            entities = self.repository.search_entities(
                None,
                entity_type=EntityType.HAWKER_CENTRE.value,
                limit=100,
            )
        except (psycopg.Error, sqlite3.Error):
            return self.fallback.discover_near(latitude, longitude)

        places = [
            Place(
                name=entity.name,
                place_type=entity.entity_type.value,
                address=entity.address,
                postal_code=entity.postal_code,
                latitude=entity.latitude,
                longitude=entity.longitude,
            )
            for entity in entities
        ]
        if not places:
            return self.fallback.discover_near(latitude, longitude)
        return sorted(
            places,
            key=lambda place: distance_km(latitude, longitude, place),
        )[:5]

    def food_listings(self) -> list[FoodListing]:
        try:
            return self.repository.search_food_listings(limit=100)
        except (psycopg.Error, sqlite3.Error):
            return []
