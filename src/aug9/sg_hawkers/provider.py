import sqlite3
from typing import Protocol

import psycopg

from aug9.core.models import Place
from aug9.discovery.models import EntityType
from aug9.discovery.repository import DiscoveryRepository
from aug9.food_data import load_hawker_data


class HawkerProvider(Protocol):
    def discover(self, query: str | None = None) -> list[Place]: ...


class CuratedHawkerProvider:
    """Discover hawker centres represented in Aug9's curated location catalog."""

    def discover(self, query: str | None = None) -> list[Place]:
        results = [Place(**item) for item in load_hawker_data()]
        if not query:
            return results

        normalized = query.casefold().strip()
        matches = [place for place in results if normalized in place.name.casefold()]
        return matches or results


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
