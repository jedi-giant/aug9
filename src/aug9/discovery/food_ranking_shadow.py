from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aug9.core import database
from aug9.discovery.food_ranking_evaluation import (
    FoodRankingCandidate,
    FoodRankingPolicy,
)
from aug9.sg_food.provider import FoodProvider


def build_food_ranking_shadow_report(
    provider: FoodProvider,
    *,
    latitude: float,
    longitude: float,
    now: datetime | None = None,
    venue_kinds: tuple[str, ...] = (),
) -> dict[str, Any]:
    generated_at = now or datetime.now(UTC)
    venues = provider.discover(
        latitude=latitude,
        longitude=longitude,
        venue_kinds=venue_kinds,
    )
    if not venues:
        return {
            "mode": "shadow",
            "live_ranking_affected": False,
            "generated_at": generated_at.isoformat(),
            "candidate_count": 0,
            "rank_changes": 0,
            "candidates": [],
        }

    signals = _food_ranking_signals([venue.id for venue in venues], generated_at)
    candidates = []
    for venue in venues:
        signal = signals.get(venue.id, {})
        candidates.append(
            FoodRankingCandidate(
                id=venue.id,
                name=venue.name,
                distance_km=venue.distance_km or 0.0,
                relevance_score=0.8,
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
    rows = []
    for proposed_rank, item in enumerate(proposed, start=1):
        venue = venue_by_id[item.candidate.id]
        current_rank = current_ranks[venue.id]
        rows.append(
            {
                "entity_id": venue.id,
                "name": venue.name,
                "address": venue.address,
                "venue_kind": venue.venue_kind,
                "distance_km": venue.distance_km,
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
    return {
        "mode": "shadow",
        "live_ranking_affected": False,
        "generated_at": generated_at.isoformat(),
        "origin": {"latitude": latitude, "longitude": longitude},
        "candidate_count": len(rows),
        "rank_changes": sum(1 for row in rows if row["rank_change"] != 0),
        "candidates": rows,
    }


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
