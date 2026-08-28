from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

import httpx

from aug9.core import database
from aug9.discovery.models import GooglePlaceLink
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


GOOGLE_PLACES_BASE_URL = "https://places.googleapis.com/v1"
MINIMUM_MATCH_CONFIDENCE = 0.85
LOW_RATING_THRESHOLD = 2.5
MINIMUM_RATING_COUNT = 10


@dataclass(frozen=True)
class FoodPlaceCandidate:
    entity_id: str
    name: str
    address: str
    postal_code: str | None
    latitude: float
    longitude: float


@dataclass(frozen=True)
class PlaceSearchResult:
    place_id: str
    name: str
    address: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class RatingSnapshot:
    place_id: str
    rating: float | None
    rating_count: int
    google_maps_uri: str | None


@dataclass(frozen=True)
class LinkSummary:
    received: int
    linked: int
    rejected: int


class GooglePlacesClient:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        requests_per_second: float = 5.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Google Places API key is required")
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=15, follow_redirects=True)
        self.minimum_interval = 1.0 / requests_per_second
        self._last_request_at = 0.0

    def search(self, candidate: FoodPlaceCandidate) -> list[PlaceSearchResult]:
        self._pace()
        response = self.client.post(
            f"{GOOGLE_PLACES_BASE_URL}/places:searchText",
            headers={
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": (
                    "places.id,places.displayName,places.formattedAddress,"
                    "places.location"
                ),
            },
            json={
                "textQuery": f"{candidate.name} {candidate.address}",
                "regionCode": "SG",
                "languageCode": "en",
                "maxResultCount": 5,
                "locationBias": {
                    "circle": {
                        "center": {
                            "latitude": candidate.latitude,
                            "longitude": candidate.longitude,
                        },
                        "radius": 500.0,
                    }
                },
            },
        )
        response.raise_for_status()
        results = []
        for place in response.json().get("places", []):
            location = place.get("location") or {}
            display_name = place.get("displayName") or {}
            results.append(
                PlaceSearchResult(
                    place_id=place["id"],
                    name=display_name.get("text", ""),
                    address=place.get("formattedAddress", ""),
                    latitude=location.get("latitude"),
                    longitude=location.get("longitude"),
                )
            )
        return results

    def rating(self, place_id: str) -> RatingSnapshot:
        self._pace()
        response = self.client.get(
            f"{GOOGLE_PLACES_BASE_URL}/places/{place_id}",
            headers={
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "id,rating,userRatingCount,googleMapsUri",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return RatingSnapshot(
            place_id=payload.get("id", place_id),
            rating=payload.get("rating"),
            rating_count=int(payload.get("userRatingCount", 0)),
            google_maps_uri=payload.get("googleMapsUri"),
        )

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.minimum_interval:
            time.sleep(self.minimum_interval - elapsed)
        self._last_request_at = time.monotonic()


class GoogleFoodPlaceLinker:
    def __init__(
        self,
        repository: DiscoveryRepository,
        places: GooglePlacesClient,
    ) -> None:
        self.repository = repository
        self.places = places

    def run(self, *, limit: int = 50) -> LinkSummary:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        candidates = self._unlinked_candidates(limit)
        if not candidates:
            return LinkSummary(0, 0, 0)
        links: list[GooglePlaceLink] = []
        attempts: list[tuple[str, str]] = []
        reserved_place_ids = {
            link.place_id
            for link in self.repository.list_google_place_links(limit=20000)
        }
        for candidate in candidates:
            try:
                results = self.places.search(candidate)
            except httpx.HTTPError:
                continue
            match = select_high_confidence_match(candidate, results)
            if match is None:
                attempts.append((candidate.entity_id, "rejected"))
                continue
            result, confidence = match
            if result.place_id in reserved_place_ids:
                attempts.append((candidate.entity_id, "place_id_collision"))
                continue
            reserved_place_ids.add(result.place_id)
            links.append(
                GooglePlaceLink(
                    entity_id=candidate.entity_id,
                    place_id=result.place_id,
                    match_confidence=confidence,
                )
            )
            attempts.append((candidate.entity_id, "linked"))
        self.repository.save_google_place_link_batch(links, attempts)
        return LinkSummary(
            len(candidates), len(links), len(candidates) - len(links)
        )

    @staticmethod
    def _unlinked_candidates(limit: int) -> list[FoodPlaceCandidate]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT e.id, e.name, COALESCE(e.address, ''), e.postal_code,
                   e.latitude, e.longitude
            FROM discovery_entities e
            JOIN discovery_source_records sfa ON sfa.entity_id = e.id
            LEFT JOIN discovery_google_place_links google_link
              ON google_link.entity_id = e.id
            LEFT JOIN discovery_google_place_link_attempts attempt
              ON attempt.entity_id = e.id
            WHERE e.status = 'active' AND sfa.source_id = {p}
              AND e.latitude IS NOT NULL AND e.longitude IS NOT NULL
              AND google_link.entity_id IS NULL
              AND attempt.entity_id IS NULL
            ORDER BY e.id
            LIMIT {p}
            """,
            (SFA_SOURCE_ID, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [FoodPlaceCandidate(*row) for row in rows]

def select_high_confidence_match(
    candidate: FoodPlaceCandidate,
    results: list[PlaceSearchResult],
) -> tuple[PlaceSearchResult, float] | None:
    scored = []
    for result in results:
        name_score = SequenceMatcher(
            None, _normalise(candidate.name), _normalise(result.name)
        ).ratio()
        postal_match = bool(
            candidate.postal_code
            and re.search(rf"\b{re.escape(candidate.postal_code)}\b", result.address)
        )
        distance_km = _distance_km(candidate, result)
        location_match = postal_match or (
            distance_km is not None and distance_km <= 0.2
        )
        if name_score < 0.8 or not location_match:
            continue
        location_score = 1.0 if postal_match else max(0.0, 1.0 - distance_km / 0.5)
        confidence = round(0.7 * name_score + 0.3 * location_score, 4)
        if confidence >= MINIMUM_MATCH_CONFIDENCE:
            scored.append((confidence, result))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.03:
        return None
    return scored[0][1], scored[0][0]


def build_google_rating_gate_report(
    repository: DiscoveryRepository,
    places: GooglePlacesClient,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    links = repository.list_google_place_links(limit=limit)
    conflicts = _trusted_positive_evidence_entities()
    decisions = []
    failures = 0
    for link in links:
        try:
            snapshot = places.rating(link.place_id)
        except httpx.HTTPError:
            failures += 1
            continue
        if snapshot.rating is None or snapshot.rating >= LOW_RATING_THRESHOLD:
            decision = "eligible"
        elif snapshot.rating_count < MINIMUM_RATING_COUNT:
            decision = "insufficient_reviews"
        elif link.entity_id in conflicts:
            decision = "conflicting_evidence_review"
        else:
            decision = "shadow_suppress"
        decisions.append(
            {
                "entity_id": link.entity_id,
                "place_id": link.place_id,
                "rating": snapshot.rating,
                "rating_count": snapshot.rating_count,
                "decision": decision,
                "google_maps_uri": snapshot.google_maps_uri,
            }
        )
    counts: dict[str, int] = {}
    for item in decisions:
        counts[item["decision"]] = counts.get(item["decision"], 0) + 1
    return {
        "mode": "shadow",
        "generated_at": datetime.now(UTC).isoformat(),
        "threshold": LOW_RATING_THRESHOLD,
        "minimum_rating_count": MINIMUM_RATING_COUNT,
        "linked_places_checked": len(links),
        "successful_checks": len(decisions),
        "failed_checks": failures,
        "decisions": counts,
        "affected_venues": [
            item for item in decisions if item["decision"] != "eligible"
        ],
    }


def _trusted_positive_evidence_entities() -> set[str]:
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT entity_id
        FROM discovery_food_evidence
        WHERE dimension = 'food_quality' AND direction = 'positive'
          AND evidence_type = 'editorial' AND commercial_status = 'organic'
          AND (expires_at IS NULL OR expires_at >= CURRENT_TIMESTAMP)
        """
    )
    entity_ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return entity_ids


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _distance_km(
    candidate: FoodPlaceCandidate,
    result: PlaceSearchResult,
) -> float | None:
    if result.latitude is None or result.longitude is None:
        return None
    lat1, lon1, lat2, lon2 = map(
        math.radians,
        (candidate.latitude, candidate.longitude, result.latitude, result.longitude),
    )
    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_longitude / 2) ** 2
    )
    return 6371.0 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
