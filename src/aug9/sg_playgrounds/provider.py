from __future__ import annotations

import math
import json
import sqlite3
from dataclasses import dataclass
from typing import Protocol

import psycopg

from aug9.core import database
from aug9.discovery.repository import DiscoveryRepository


@dataclass(frozen=True)
class Playground:
    id: str
    name: str
    address: str | None
    latitude: float
    longitude: float
    distance_km: float | None = None
    age_fit: str | None = None
    features: tuple[str, ...] = ()
    has_water_play: bool = False
    is_sheltered: bool = False


class PlaygroundProvider(Protocol):
    def discover(self, *, latitude: float | None, longitude: float | None) -> list[Playground]: ...


class DatabasePlaygroundProvider:
    def __init__(self, repository: DiscoveryRepository | None = None, *, limit: int = 5) -> None:
        if limit < 1 or limit > 20:
            raise ValueError("limit must be between 1 and 20")
        self.repository = repository or DiscoveryRepository()
        self.limit = limit

    def discover(self, *, latitude: float | None, longitude: float | None) -> list[Playground]:
        try:
            conn = database.get_connection()
            cursor = conn.cursor()
            p = database.placeholder()
            cursor.execute(
                f"""
                SELECT e.id, e.name, e.address, e.latitude, e.longitude,
                       sr.raw_payload
                FROM discovery_entities e
                LEFT JOIN discovery_source_records sr ON sr.entity_id = e.id
                WHERE e.entity_type = 'playground' AND e.status = 'active'
                ORDER BY e.quality_score DESC, e.name ASC
                LIMIT {p}
                """,
                (100,),
            )
            rows = cursor.fetchall()
            conn.close()
        except (psycopg.Error, sqlite3.Error):
            return []
        results = []
        for row in rows:
            if row[3] is None or row[4] is None:
                continue
            raw = row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}")
            properties = raw.get("properties", {})
            results.append(
                Playground(
                    id=row[0],
                    name=row[1],
                    address=row[2],
                    latitude=row[3],
                    longitude=row[4],
                    distance_km=(
                        self._distance(latitude, longitude, row[3], row[4])
                        if latitude is not None and longitude is not None
                        else None
                    ),
                    age_fit=properties.get("age_fit"),
                    features=tuple(properties.get("features") or ()),
                    has_water_play=bool(properties.get("has_water_play")),
                    is_sheltered=bool(properties.get("is_sheltered")),
                )
            )
        if latitude is not None and longitude is not None:
            results.sort(key=lambda item: item.distance_km or float("inf"))
        return results[: self.limit]

    @staticmethod
    def _distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
