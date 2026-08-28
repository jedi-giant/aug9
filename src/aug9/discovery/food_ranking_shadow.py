from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from aug9.core import database
from aug9.discovery.food_ranking_evaluation import (
    FoodRankingCandidate,
    FoodRankingPolicy,
)
from aug9.sg_food.provider import DatabaseFoodProvider, FoodProvider


def build_food_ranking_shadow_report(
    provider: FoodProvider,
    *,
    latitude: float,
    longitude: float,
    now: datetime | None = None,
    venue_kinds: tuple[str, ...] = (),
    pool_limit: int = 250,
    display_limit: int = 12,
    request_text: str = "food",
) -> dict[str, Any]:
    if pool_limit < 1 or pool_limit > 500:
        raise ValueError("pool_limit must be between 1 and 500")
    if display_limit < 1 or display_limit > 50:
        raise ValueError("display_limit must be between 1 and 50")
    if display_limit > pool_limit:
        raise ValueError("display_limit cannot exceed pool_limit")
    generated_at = now or datetime.now(UTC)
    request_category = _request_category(request_text)
    if isinstance(provider, DatabaseFoodProvider):
        venues = provider.discover_pool(
            latitude=latitude,
            longitude=longitude,
            venue_kinds=venue_kinds,
            limit=pool_limit,
        )
    else:
        venues = provider.discover(
            latitude=latitude,
            longitude=longitude,
            venue_kinds=venue_kinds,
        )[:pool_limit]
    if not venues:
        return {
            "mode": "shadow",
            "live_ranking_affected": False,
            "generated_at": generated_at.isoformat(),
            "request": {"text": request_text, "category": request_category},
            "pool_candidate_count": 0,
            "displayed_candidate_count": 0,
            "editorial_candidate_count": 0,
            "rank_changes": 0,
            "shortlist_count": 0,
            "recommended_shortlist": [],
            "candidates": [],
        }

    signals = _food_ranking_signals([venue.id for venue in venues], generated_at)
    candidates = []
    for venue in venues:
        signal = signals.get(venue.id, {})
        candidate_category = _candidate_category(venue.name)
        candidates.append(
            FoodRankingCandidate(
                id=venue.id,
                name=venue.name,
                distance_km=venue.distance_km or 0.0,
                relevance_score=_relevance_score(
                    candidate_category, request_category
                ),
                provenance_score=0.9 if signal.get("editorial_count", 0) else 0.8,
                freshness_score=signal.get("freshness_score", 0.5),
                positive_organic_editorial_records=signal.get(
                    "editorial_count", 0
                ),
            )
        )

    proposed = FoodRankingPolicy().rank(candidates)
    current_ranks = {venue.id: rank for rank, venue in enumerate(venues, start=1)}
    venue_by_id = {venue.id: venue for venue in venues}
    all_rows = []
    for proposed_rank, item in enumerate(proposed, start=1):
        venue = venue_by_id[item.candidate.id]
        current_rank = current_ranks[venue.id]
        all_rows.append(
            {
                "entity_id": venue.id,
                "name": venue.name,
                "address": venue.address,
                "postal_code": venue.postal_code,
                "venue_kind": venue.venue_kind,
                "safe_grade": venue.safe_grade,
                "business_type": venue.business_type,
                "candidate_category": _candidate_category(venue.name),
                "distance_km": venue.distance_km,
                "latitude": venue.latitude,
                "longitude": venue.longitude,
                "current_distance_rank": current_rank,
                "proposed_rank": proposed_rank,
                "rank_change": current_rank - proposed_rank,
                "proposed_score": item.score,
                "positive_organic_editorial_records": (
                    item.candidate.positive_organic_editorial_records
                ),
                "factors": [factor.__dict__ for factor in item.factors],
            }
        )
    displayed_rows = all_rows[:display_limit]
    shortlist = _select_shortlist(
        all_rows, request_category=request_category, limit=3
    )
    coordinate_groups: dict[tuple[float | None, float | None], int] = {}
    for venue in venues:
        key = (venue.latitude, venue.longitude)
        coordinate_groups[key] = coordinate_groups.get(key, 0) + 1
    largest_tie = max(coordinate_groups.values(), default=0)
    return {
        "mode": "shadow",
        "live_ranking_affected": False,
        "generated_at": generated_at.isoformat(),
        "origin": {"latitude": latitude, "longitude": longitude},
        "request": {
            "text": request_text,
            "category": request_category,
        },
        "pool_candidate_count": len(all_rows),
        "displayed_candidate_count": len(displayed_rows),
        "editorial_candidate_count": sum(
            1
            for row in all_rows
            if row["positive_organic_editorial_records"] > 0
        ),
        "distance_ties": {
            "coordinate_group_count": len(coordinate_groups),
            "largest_same_coordinate_group": largest_tie,
            "alphabetical_tie_break_is_quality_signal": False,
        },
        "rank_changes": sum(
            1 for row in displayed_rows if row["rank_change"] != 0
        ),
        "shortlist_count": len(shortlist),
        "recommended_shortlist": shortlist,
        "candidates": displayed_rows,
    }


def _select_shortlist(
    ranked_rows: list[dict[str, Any]],
    *,
    request_category: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 5:
        raise ValueError("shortlist limit must be between 1 and 5")
    if not ranked_rows:
        return []
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    supported = next(
        (
            row
            for row in ranked_rows
            if row["positive_organic_editorial_records"] > 0
            and _is_suitable(row["candidate_category"], request_category)
        ),
        None,
    )
    if supported is not None:
        selected.append(_shortlist_item(supported, "best_supported"))
        selected_ids.add(supported["entity_id"])

    closest = min(
        (
            row
            for row in ranked_rows
            if row["entity_id"] not in selected_ids
            and _is_suitable(row["candidate_category"], request_category)
        ),
        key=lambda row: (
            int(row["distance_km"] / 0.1),
            0 if row["candidate_category"] == request_category else 1,
            row["distance_km"],
            row["name"].casefold(),
        ),
        default=None,
    )
    if closest is not None and len(selected) < limit:
        selected.append(_shortlist_item(closest, "closest_suitable"))
        selected_ids.add(closest["entity_id"])

    used_locations = {
        _coordinate_key(row)
        for row in ranked_rows
        if row["entity_id"] in selected_ids
    }
    alternatives = [
        row
        for row in ranked_rows
        if row["entity_id"] not in selected_ids
        and _coordinate_key(row) not in used_locations
        and _is_suitable(row["candidate_category"], request_category)
    ]
    for row in alternatives:
        if len(selected) >= limit:
            break
        selected.append(_shortlist_item(row, "nearby_alternative"))
        selected_ids.add(row["entity_id"])
        used_locations.add(_coordinate_key(row))
    return selected


def _shortlist_item(row: dict[str, Any], role: str) -> dict[str, Any]:
    reasons = {
        "best_supported": "Strongest active organic editorial support nearby",
        "closest_suitable": (
            "Best request-compatible licensed option in the closest 100 m tier"
        ),
        "nearby_alternative": "Nearby option from a different mapped location",
    }
    return {
        "role": role,
        "reason": reasons[role],
        "entity_id": row["entity_id"],
        "name": row["name"],
        "address": row["address"],
        "postal_code": row["postal_code"],
        "venue_kind": row["venue_kind"],
        "safe_grade": row["safe_grade"],
        "business_type": row["business_type"],
        "candidate_category": row["candidate_category"],
        "distance_km": row["distance_km"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "proposed_score": row["proposed_score"],
        "positive_organic_editorial_records": row[
            "positive_organic_editorial_records"
        ],
    }


def _coordinate_key(row: dict[str, Any]) -> tuple[float | None, float | None]:
    latitude = row.get("latitude")
    longitude = row.get("longitude")
    return (
        round(latitude, 5) if latitude is not None else None,
        round(longitude, 5) if longitude is not None else None,
    )


_BEVERAGE_TERMS = {
    "beverage", "beverages", "coffee", "drink", "drinks", "juice", "kopi",
    "smoothie", "tea",
}
_DESSERT_TERMS = {
    "bakery", "cake", "cakes", "chendol", "dessert", "desserts", "gelato",
    "ice cream", "tutu",
}
_MEAL_TERMS = {
    "biryani", "chicken", "curry", "fish", "kway teow", "laksa", "mee",
    "nasi", "noodle", "noodles", "porridge", "prata", "rice", "satay",
    "seafood", "wanton",
}


def _candidate_category(name: str) -> str:
    normalised = " ".join(re.findall(r"[a-z0-9]+", name.casefold()))
    if _contains_term(normalised, _BEVERAGE_TERMS):
        return "beverage"
    if _contains_term(normalised, _DESSERT_TERMS):
        return "dessert"
    if _contains_term(normalised, _MEAL_TERMS):
        return "meal"
    return "unknown"


def _request_category(text: str) -> str:
    normalised = " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
    if _contains_term(normalised, _BEVERAGE_TERMS):
        return "beverage"
    if _contains_term(normalised, _DESSERT_TERMS):
        return "dessert"
    return "meal"


def _contains_term(value: str, terms: set[str]) -> bool:
    padded = f" {value} "
    return any(f" {term} " in padded for term in terms)


def _is_suitable(candidate_category: str, request_category: str) -> bool:
    return candidate_category in {request_category, "unknown"}


def _relevance_score(candidate_category: str, request_category: str) -> float:
    if candidate_category == request_category:
        return 0.95
    if candidate_category == "unknown":
        return 0.7
    return 0.3


def _food_ranking_signals(
    entity_ids: list[str], now: datetime
) -> dict[str, dict[str, Any]]:
    if not entity_ids:
        return {}
    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    placeholders = ", ".join(p for _ in entity_ids)
    cursor.execute(
        f"""
        SELECT entity_id,
               COUNT(*) AS editorial_count,
               MAX(observed_at) AS latest_observed_at
        FROM discovery_food_evidence
        WHERE entity_id IN ({placeholders})
          AND dimension = 'food_quality'
          AND evidence_type = 'editorial'
          AND direction = 'positive'
          AND commercial_status = 'organic'
          AND (expires_at IS NULL OR expires_at >= {p})
        GROUP BY entity_id
        """,
        (*entity_ids, now.isoformat()),
    )
    signals: dict[str, dict[str, Any]] = {}
    for entity_id, count, observed_at in cursor.fetchall():
        signals[entity_id] = {
            "editorial_count": int(count),
            "freshness_score": _freshness_score(observed_at, now),
        }
    conn.close()
    return signals


def _freshness_score(observed_at: datetime | str | None, now: datetime) -> float:
    if observed_at is None:
        return 0.5
    value = (
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if isinstance(observed_at, str)
        else observed_at
    )
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    age_days = max(0, (now - value).days)
    if age_days <= 90:
        return 0.9
    if age_days <= 365:
        return 0.7
    return 0.4
