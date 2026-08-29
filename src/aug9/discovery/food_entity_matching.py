from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from aug9.core import database
from aug9.discovery.models import RelationshipType
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


DEFAULT_SOURCE_IDS = (
    "singapore_food_media_curated_2024_2026",
    "jd_google_maps_food_places",
)


@dataclass(frozen=True)
class EntityRow:
    id: str
    name: str
    address: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    source_id: str


@dataclass(frozen=True)
class MatchDecision:
    source_entity_id: str
    source_name: str
    canonical_entity_id: str | None
    canonical_name: str | None
    confidence: float
    outcome: str
    reason: str


class FoodEntityMatcher:
    def __init__(
        self,
        *,
        source_ids: tuple[str, ...] = DEFAULT_SOURCE_IDS,
        threshold: float = 0.88,
        ambiguity_margin: float = 0.05,
    ) -> None:
        if not source_ids:
            raise ValueError("At least one source ID is required")
        if not 0.5 <= threshold <= 1:
            raise ValueError("threshold must be between 0.5 and 1")
        self.source_ids = source_ids
        self.threshold = threshold
        self.ambiguity_margin = ambiguity_margin

    def run(self, *, apply: bool = False, limit: int = 5000) -> dict:
        if limit < 1 or limit > 50_000:
            raise ValueError("limit must be between 1 and 50000")
        sources, canonicals = self._fetch(limit)
        decisions = [self._match(source, canonicals) for source in sources]
        if apply:
            self._apply(decisions)
        counts: dict[str, int] = {}
        for item in decisions:
            counts[item.outcome] = counts.get(item.outcome, 0) + 1
        return {
            "mode": "apply" if apply else "shadow",
            "source_entity_count": len(sources),
            "canonical_candidate_count": len(canonicals),
            "outcomes": counts,
            "decisions": [item.__dict__ for item in decisions],
        }

    def _fetch(self, limit: int) -> tuple[list[EntityRow], list[EntityRow]]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        source_placeholders = ", ".join(p for _ in self.source_ids)
        cursor.execute(
            f"""
            SELECT DISTINCT e.id, e.name, e.address, e.postal_code,
                   e.latitude, e.longitude, sr.source_id
            FROM discovery_entities e
            JOIN discovery_source_records sr ON sr.entity_id = e.id
            WHERE sr.source_id IN ({source_placeholders})
              AND e.entity_type IN ('food_venue', 'food_stall')
              AND e.status = 'active'
            ORDER BY e.name
            LIMIT {p}
            """,
            (*self.source_ids, limit),
        )
        sources = [EntityRow(*row) for row in cursor.fetchall()]
        cursor.execute(
            f"""
            SELECT DISTINCT e.id, e.name, e.address, e.postal_code,
                   e.latitude, e.longitude, sr.source_id
            FROM discovery_entities e
            JOIN discovery_source_records sr ON sr.entity_id = e.id
            WHERE sr.source_id = {p}
              AND e.entity_type IN ('food_venue', 'food_stall')
              AND e.status = 'active'
            ORDER BY e.name
            """,
            (SFA_SOURCE_ID,),
        )
        canonicals = [EntityRow(*row) for row in cursor.fetchall()]
        conn.close()
        return sources, canonicals

    def _match(self, source: EntityRow, canonicals: list[EntityRow]) -> MatchDecision:
        candidates = []
        for canonical in canonicals:
            score, reason = self._score(source, canonical)
            if score > 0:
                candidates.append((score, canonical, reason))
        candidates.sort(key=lambda item: (-item[0], item[1].name.casefold()))
        if not candidates or candidates[0][0] < self.threshold:
            best = candidates[0] if candidates else None
            return MatchDecision(
                source.id,
                source.name,
                best[1].id if best else None,
                best[1].name if best else None,
                round(best[0], 4) if best else 0.0,
                "unmatched",
                best[2] if best else "no plausible candidate",
            )
        top = candidates[0]
        if len(candidates) > 1 and top[0] - candidates[1][0] < self.ambiguity_margin:
            return MatchDecision(
                source.id,
                source.name,
                top[1].id,
                top[1].name,
                round(top[0], 4),
                "ambiguous",
                "top candidates are too close",
            )
        return MatchDecision(
            source.id,
            source.name,
            top[1].id,
            top[1].name,
            round(top[0], 4),
            "matched",
            top[2],
        )

    @classmethod
    def _score(cls, source: EntityRow, canonical: EntityRow) -> tuple[float, str]:
        same_postal = bool(
            source.postal_code
            and canonical.postal_code
            and source.postal_code == canonical.postal_code
        )
        coordinates_close = bool(
            None not in (
                source.latitude,
                source.longitude,
                canonical.latitude,
                canonical.longitude,
            )
            and abs(source.latitude - canonical.latitude) <= 0.001
            and abs(source.longitude - canonical.longitude) <= 0.001
        )
        if not same_postal and not coordinates_close:
            return 0.0, "insufficient location agreement"
        source_name = cls._normalise(source.name)
        canonical_name = cls._normalise(canonical.name)
        name_score = SequenceMatcher(None, source_name, canonical_name).ratio()
        distance = cls._distance(source, canonical) if coordinates_close else None
        if same_postal and source_name == canonical_name:
            return 1.0, "exact normalised name and postal code"
        if same_postal and name_score >= 0.85:
            return 0.9 + 0.1 * name_score, "strong name match at the same postal code"
        if distance is not None and distance <= 0.1 and name_score >= 0.88:
            return 0.88 + 0.1 * name_score, "strong name match within 100 m"
        if distance is not None and distance <= 0.03 and name_score >= 0.75:
            return 0.85 + 0.1 * name_score, "name match within 30 m"
        return 0.0, "insufficient identity agreement"

    def _apply(self, decisions: list[MatchDecision]) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            for item in decisions:
                cursor.execute(
                    f"""
                    DELETE FROM discovery_entity_relationships
                    WHERE child_entity_id = {p} AND relationship_type = {p}
                    """,
                    (item.source_entity_id, RelationshipType.SAME_AS.value),
                )
                if item.outcome != "matched" or item.canonical_entity_id is None:
                    continue
                cursor.execute(
                    f"""
                    INSERT INTO discovery_entity_relationships (
                        parent_entity_id, child_entity_id, relationship_type, source_id
                    ) VALUES ({p}, {p}, {p}, {p})
                    ON CONFLICT(parent_entity_id, child_entity_id, relationship_type)
                    DO UPDATE SET source_id = excluded.source_id
                    """,
                    (
                        item.canonical_entity_id,
                        item.source_entity_id,
                        RelationshipType.SAME_AS.value,
                        self._source_id_for(item.source_entity_id),
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _source_id_for(self, entity_id: str) -> str:
        for source_id in self.source_ids:
            if f":{source_id}:" in entity_id:
                return source_id
        raise ValueError(f"Cannot resolve source for entity {entity_id}")

    @staticmethod
    def _normalise(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    @staticmethod
    def _distance(left: EntityRow, right: EntityRow) -> float | None:
        if None in (left.latitude, left.longitude, right.latitude, right.longitude):
            return None
        lat1, lon1, lat2, lon2 = map(
            math.radians,
            (left.latitude, left.longitude, right.latitude, right.longitude),
        )
        dlat, dlon = lat2 - lat1, lon2 - lon1
        value = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return 6371.0 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
