import sqlite3
from typing import Protocol

import psycopg

from aug9.core.models import Place
from aug9.discovery.models import EntityType
from aug9.discovery.repository import DiscoveryRepository


class HotelProvider(Protocol):
    def discover(self, query: str | None = None) -> list[Place]: ...


class DatabaseHotelProvider:
    def __init__(
        self,
        repository: DiscoveryRepository | None = None,
        *,
        limit: int = 12,
    ) -> None:
        self.repository = repository or DiscoveryRepository()
        self.limit = limit

    def discover(self, query: str | None = None) -> list[Place]:
        try:
            entities = self.repository.search_entities(
                query,
                entity_type=EntityType.HOTEL.value,
                limit=self.limit,
            )
        except (psycopg.Error, sqlite3.Error):
            return []
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
