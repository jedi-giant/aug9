import math
import sqlite3
from dataclasses import dataclass
from typing import Protocol

import psycopg

from aug9.core import database
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


@dataclass(frozen=True)
class FoodVenue:
    id: str
    name: str
    venue_kind: str
    address: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    safe_grade: str
    business_type: str
    distance_km: float | None = None


class FoodProvider(Protocol):
    def discover(
        self,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        query: str | None = None,
        venue_kinds: tuple[str, ...] = (),
    ) -> list[FoodVenue]: ...


class DatabaseFoodProvider:
    def __init__(
        self,
        *,
        limit: int = 8,
        max_distance_km: float = 3.0,
    ) -> None:
        if limit < 1 or limit > 25:
            raise ValueError("limit must be between 1 and 25")
        if max_distance_km <= 0 or max_distance_km > 20:
            raise ValueError("max_distance_km must be between 0 and 20")
        self.limit = limit
        self.max_distance_km = max_distance_km

    def discover(
        self,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        query: str | None = None,
        venue_kinds: tuple[str, ...] = (),
    ) -> list[FoodVenue]:
        return self._discover(
            latitude=latitude,
            longitude=longitude,
            query=query,
            venue_kinds=venue_kinds,
            result_limit=self.limit,
        )

    def discover_pool(
        self,
        *,
        latitude: float,
        longitude: float,
        venue_kinds: tuple[str, ...] = (),
        limit: int = 250,
    ) -> list[FoodVenue]:
        """Return a larger bounded pool for offline ranking evaluation only."""
        if limit < 1 or limit > 500:
            raise ValueError("pool limit must be between 1 and 500")
        return self._discover(
            latitude=latitude,
            longitude=longitude,
            query=None,
            venue_kinds=venue_kinds,
            result_limit=limit,
        )

    def _discover(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        query: str | None,
        venue_kinds: tuple[str, ...],
        result_limit: int,
    ) -> list[FoodVenue]:
        try:
            rows = self._fetch_candidates(
                latitude=latitude,
                longitude=longitude,
                query=query,
                venue_kinds=venue_kinds,
            )
        except (psycopg.Error, sqlite3.Error):
            return []

        venues = [FoodVenue(*row) for row in rows]
        if latitude is None or longitude is None:
            return venues[:result_limit]

        nearby = []
        for venue in venues:
            if venue.latitude is None or venue.longitude is None:
                continue
            distance = _distance_km(
                latitude, longitude, venue.latitude, venue.longitude
            )
            if distance <= self.max_distance_km:
                nearby.append(
                    FoodVenue(
                        **{
                            **venue.__dict__,
                            "distance_km": round(distance, 2),
                        }
                    )
                )
        nearby.sort(
            key=lambda item: (
                item.distance_km if item.distance_km is not None else math.inf,
                item.name,
            )
        )
        return nearby[:result_limit]

    def _fetch_candidates(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        query: str | None,
        venue_kinds: tuple[str, ...],
    ) -> list[tuple]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        conditions = [
            "e.status = 'active'",
            f"sfa.source_id = {p}",
        ]
        params: list[object] = [SFA_SOURCE_ID]
        if latitude is not None and longitude is not None:
            latitude_delta = self.max_distance_km / 111.0
            longitude_scale = max(math.cos(math.radians(latitude)), 0.1)
            longitude_delta = self.max_distance_km / (111.0 * longitude_scale)
            conditions.extend(
                [
                    f"e.latitude BETWEEN {p} AND {p}",
                    f"e.longitude BETWEEN {p} AND {p}",
                ]
            )
            params.extend(
                [
                    latitude - latitude_delta,
                    latitude + latitude_delta,
                    longitude - longitude_delta,
                    longitude + longitude_delta,
                ]
            )
        elif query:
            conditions.append(f"LOWER(e.name || ' ' || e.address) LIKE {p}")
            params.append(f"%{query.casefold()}%")
        if venue_kinds:
            placeholders = ", ".join(p for _ in venue_kinds)
            conditions.append(f"fp.venue_kind IN ({placeholders})")
            params.extend(venue_kinds)

        result_limit = f"LIMIT {p}" if latitude is None or longitude is None else ""
        if result_limit:
            params.append(self.limit)
        cursor.execute(
            f"""
            SELECT e.id, e.name, fp.venue_kind, e.address, e.postal_code,
                   e.latitude, e.longitude, fs.safe_grade, fs.business_type
            FROM discovery_entities e
            JOIN discovery_source_records sfa ON sfa.entity_id = e.id
            JOIN discovery_food_profiles fp ON fp.entity_id = e.id
            JOIN discovery_food_safety_profiles fs ON fs.entity_id = e.id
            WHERE {' AND '.join(conditions)}
            ORDER BY e.quality_score DESC, e.name ASC
            {result_limit}
            """,
            tuple(params),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows


def _distance_km(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> float:
    lat1, lon1, lat2, lon2 = map(
        math.radians,
        (
            origin_latitude,
            origin_longitude,
            destination_latitude,
            destination_longitude,
        ),
    )
    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_longitude / 2) ** 2
    )
    return 6371.0 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
