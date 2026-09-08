from __future__ import annotations

import math
import json
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
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
    min_age: int | None = None
    max_age: int | None = None
    aliases: tuple[str, ...] = ()


class PlaygroundProvider(Protocol):
    def discover(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        child_ages: tuple[int, ...] = (),
        water_play: bool = False,
        sheltered: bool = False,
        prefer_sheltered: bool = False,
        name_query: str | None = None,
    ) -> list[Playground]: ...


class DatabasePlaygroundProvider:
    def __init__(self, repository: DiscoveryRepository | None = None, *, limit: int = 3) -> None:
        if limit < 1 or limit > 20:
            raise ValueError("limit must be between 1 and 20")
        self.repository = repository or DiscoveryRepository()
        self.limit = limit

    def discover(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        child_ages: tuple[int, ...] = (),
        water_play: bool = False,
        sheltered: bool = False,
        prefer_sheltered: bool = False,
        name_query: str | None = None,
    ) -> list[Playground]:
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
                (5000 if name_query else 100,),
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
                    min_age=properties.get("min_age"),
                    max_age=properties.get("max_age"),
                    aliases=tuple(properties.get("aliases") or ()),
                )
            )
        if name_query:
            results = self._match_name(results, name_query)
        if child_ages:
            results = [
                item
                for item in results
                if item.min_age is not None
                and item.max_age is not None
                and all(item.min_age <= age <= item.max_age for age in child_ages)
            ]
        if water_play:
            results = [item for item in results if item.has_water_play]
        if sheltered:
            results = [item for item in results if item.is_sheltered]
        results.sort(
            key=lambda item: (
                (
                    item.distance_km
                    if item.distance_km is not None
                    else float("inf")
                )
                - (2.0 if prefer_sheltered and item.is_sheltered else 0.0),
                item.name,
            )
        )
        return results[: self.limit]

    @classmethod
    def _match_name(
        cls,
        playgrounds: list[Playground],
        query: str,
    ) -> list[Playground]:
        wanted = cls._normalise_name(query)
        scored: list[tuple[float, Playground]] = []
        for playground in playgrounds:
            candidate_names = (playground.name, *playground.aliases)
            score = 0.0
            for candidate_name in candidate_names:
                name = cls._normalise_name(candidate_name)
                candidate_score = (
                    1.0
                    if name == wanted
                    else SequenceMatcher(None, wanted, name).ratio()
                )
                if wanted in name or name in wanted:
                    candidate_score = max(candidate_score, 0.9)
                score = max(score, candidate_score)
            if score >= 0.78:
                scored.append((score, playground))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].distance_km
                if item[1].distance_km is not None
                else float("inf"),
            )
        )
        if not scored:
            return []
        if (
            scored[0][0] < 1.0
            and len(scored) > 1
            and scored[0][0] - scored[1][0] < 0.08
        ):
            return []
        return [scored[0][1]]

    @staticmethod
    def _normalise_name(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    @staticmethod
    def _distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
