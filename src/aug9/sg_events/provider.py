import sqlite3
import math
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
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None


class EventProvider(Protocol):
    def discover(
        self,
        *,
        query: str | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        category: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> list[EventListing]: ...


class DatabaseEventProvider:
    def __init__(self, repository: DiscoveryRepository | None = None, *, limit: int = 12):
        self.repository = repository or DiscoveryRepository()
        self.limit = limit

    def discover(
        self,
        *,
        query=None,
        starts_after=None,
        starts_before=None,
        category=None,
        latitude=None,
        longitude=None,
    ):
        try:
            rows = self.repository.search_events(
                query=query,
                starts_after=starts_after,
                starts_before=starts_before,
                category=category,
                limit=max(self.limit, 50) if latitude is not None else self.limit,
            )
        except (psycopg.Error, sqlite3.Error):
            return []
        listings = [
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
                latitude=entity.latitude,
                longitude=entity.longitude,
                distance_km=(
                    self._distance_km(
                        latitude, longitude, entity.latitude, entity.longitude
                    )
                    if latitude is not None
                    and longitude is not None
                    and entity.latitude is not None
                    and entity.longitude is not None
                    else None
                ),
            )
            for entity, profile in rows
        ]
        if latitude is not None and longitude is not None:
            listings.sort(
                key=lambda item: (
                    item.distance_km is None,
                    item.distance_km if item.distance_km is not None else math.inf,
                    item.starts_at,
                )
            )
        return listings[: self.limit]

    @staticmethod
    def _distance_km(lat1, lon1, lat2, lon2):
        radius_km = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        value = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return round(
            radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)),
            2,
        )
