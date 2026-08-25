import sqlite3
from datetime import datetime
from typing import Protocol

import psycopg
from pydantic import BaseModel

from aug9.discovery.repository import DiscoveryRepository


class EventListing(BaseModel):
    name: str
    description: str | None = None
    address: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    category: str | None = None
    organiser: str | None = None
    ticketed: bool | None = None
    price_min: float | None = None
    currency: str = "SGD"
    booking_url: str | None = None
    source_url: str


class EventProvider(Protocol):
    def discover(
        self,
        *,
        query: str | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        category: str | None = None,
    ) -> list[EventListing]: ...


class DatabaseEventProvider:
    def __init__(self, repository: DiscoveryRepository | None = None, *, limit: int = 12):
        self.repository = repository or DiscoveryRepository()
        self.limit = limit

    def discover(self, *, query=None, starts_after=None, starts_before=None, category=None):
        try:
            rows = self.repository.search_events(
                query=query,
                starts_after=starts_after,
                starts_before=starts_before,
                category=category,
                limit=self.limit,
            )
        except (psycopg.Error, sqlite3.Error):
            return []
        return [
            EventListing(
                name=entity.name,
                description=entity.description,
                address=entity.address,
                starts_at=profile.starts_at,
                ends_at=profile.ends_at,
                category=profile.category,
                organiser=profile.organiser,
                ticketed=profile.ticketed,
                price_min=profile.price_min,
                currency=profile.currency,
                booking_url=profile.booking_url,
                source_url=profile.source_url,
            )
            for entity, profile in rows
        ]
