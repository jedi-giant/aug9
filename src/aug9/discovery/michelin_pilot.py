from __future__ import annotations

import csv
import math
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from aug9.core import database
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


@dataclass(frozen=True)
class MichelinPilotCandidate:
    external_id: str
    name: str
    latitude: float
    longitude: float
    distinction: str
    price_band: str
    cuisine: str
    source_url: str
    observed_at: str


@dataclass(frozen=True)
class MichelinMatchAlternative:
    entity_id: str
    entity_name: str
    entity_address: str | None
    distance_km: float
    name_similarity: float
    match_score: float


@dataclass(frozen=True)
class MichelinEntityMatch:
    candidate: MichelinPilotCandidate
    entity_id: str | None
    entity_name: str | None
    entity_address: str | None
    distance_km: float | None
    name_similarity: float | None
    match_score: float | None
    status: str
    alternatives: tuple[MichelinMatchAlternative, ...]


def load_michelin_pilot(path: Path) -> list[MichelinPilotCandidate]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        candidates = [
            MichelinPilotCandidate(
                external_id=row["external_id"].strip(),
                name=row["name"].strip(),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                distinction=row["distinction"].strip(),
                price_band=row["price_band"].strip(),
                cuisine=row["cuisine"].strip(),
                source_url=row["source_url"].strip(),
                observed_at=row["observed_at"].strip(),
            )
            for row in csv.DictReader(handle)
        ]
    if len(candidates) > 100:
        raise ValueError("Michelin pilot cannot exceed 100 candidates")
    return candidates


class MichelinSfaMatcher:
    def __init__(self, *, radius_km: float = 0.5) -> None:
        if radius_km <= 0 or radius_km > 2:
            raise ValueError("radius_km must be between 0 and 2")
        self.radius_km = radius_km

    def match(self, candidate: MichelinPilotCandidate) -> MichelinEntityMatch:
        nearby = self._nearby_entities(candidate)
        ranked = []
        for entity_id, name, address, latitude, longitude in nearby:
            distance = _distance_km(
                candidate.latitude,
                candidate.longitude,
                float(latitude),
                float(longitude),
            )
            similarity = SequenceMatcher(
                None, _normalise_name(candidate.name), _normalise_name(name)
            ).ratio()
            distance_score = max(0.0, 1.0 - distance / self.radius_km)
            score = 0.75 * similarity + 0.25 * distance_score
            ranked.append((score, similarity, distance, entity_id, name, address))
        if not ranked:
            return MichelinEntityMatch(
                candidate, None, None, None, None, None, None, "unmatched", ()
            )
        ranked.sort(key=lambda item: (-item[0], item[2], item[4]))
        score, similarity, distance, entity_id, name, address = ranked[0]
        runner_up_score = ranked[1][0] if len(ranked) > 1 else 0.0
        unambiguous = score - runner_up_score >= 0.08
        status = (
            "high_confidence"
            if similarity >= 0.9 and distance <= 0.25 and unambiguous
            else "review"
            if score >= 0.55
            else "unmatched"
        )
        alternatives = tuple(
            MichelinMatchAlternative(
                entity_id=item[3],
                entity_name=item[4],
                entity_address=item[5],
                distance_km=round(item[2], 3),
                name_similarity=round(item[1], 3),
                match_score=round(item[0], 3),
            )
            for item in ranked[:3]
        )
        return MichelinEntityMatch(
            candidate=candidate,
            entity_id=entity_id,
            entity_name=name,
            entity_address=address,
            distance_km=round(distance, 3),
            name_similarity=round(similarity, 3),
            match_score=round(score, 3),
            status=status,
            alternatives=alternatives,
        )

    def match_all(
        self, candidates: list[MichelinPilotCandidate]
    ) -> list[MichelinEntityMatch]:
        return [self.match(candidate) for candidate in candidates]

    def _nearby_entities(self, candidate: MichelinPilotCandidate) -> list[tuple]:
        latitude_delta = self.radius_km / 111.0
        longitude_delta = self.radius_km / (
            111.0 * max(math.cos(math.radians(candidate.latitude)), 0.1)
        )
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT e.id, e.name, e.address, e.latitude, e.longitude
            FROM discovery_entities e
            JOIN discovery_source_records sfa ON sfa.entity_id = e.id
            WHERE e.status = 'active'
              AND sfa.source_id = {p}
              AND e.latitude BETWEEN {p} AND {p}
              AND e.longitude BETWEEN {p} AND {p}
            """,
            (
                SFA_SOURCE_ID,
                candidate.latitude - latitude_delta,
                candidate.latitude + latitude_delta,
                candidate.longitude - longitude_delta,
                candidate.longitude + longitude_delta,
            ),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows


def _normalise_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", ascii_value.casefold())
    ignored = {"pte", "ltd", "restaurant", "the"}
    return " ".join(word for word in words if word not in ignored)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    values = map(math.radians, (lat1, lon1, lat2, lon2))
    origin_lat, origin_lon, destination_lat, destination_lon = values
    delta_lat = destination_lat - origin_lat
    delta_lon = destination_lon - origin_lon
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(origin_lat)
        * math.cos(destination_lat)
        * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
