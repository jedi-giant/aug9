from dataclasses import dataclass
from datetime import UTC, datetime

from aug9.core import database
from aug9.discovery.food_locations import ONEMAP_FOOD_LOCATION_SOURCE_ID
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


@dataclass(frozen=True)
class FoodCatalogReport:
    generated_at: datetime
    active_food_establishments: int
    establishments_by_kind: dict[str, int]
    establishments_by_safe_grade: dict[str, int]
    missing_postal_code: int
    missing_coordinates: int
    one_map_attempted: int
    one_map_matched: int
    one_map_rejected: int

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "active_food_establishments": self.active_food_establishments,
            "establishments_by_kind": self.establishments_by_kind,
            "establishments_by_safe_grade": self.establishments_by_safe_grade,
            "location_quality": {
                "missing_postal_code": self.missing_postal_code,
                "missing_coordinates": self.missing_coordinates,
                "one_map_attempted": self.one_map_attempted,
                "one_map_matched": self.one_map_matched,
                "one_map_rejected": self.one_map_rejected,
            },
        }


def build_food_catalog_report(
    *, now: datetime | None = None
) -> FoodCatalogReport:
    generated_at = now or datetime.now(UTC)
    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    active_sfa_filter = (
        "e.status = 'active' AND EXISTS ("
        "SELECT 1 FROM discovery_source_records sfa "
        f"WHERE sfa.source_id = {p} AND sfa.entity_id = e.id)"
    )

    cursor.execute(
        f"""
        SELECT COUNT(*),
               SUM(CASE WHEN e.postal_code IS NULL OR e.postal_code = ''
                   THEN 1 ELSE 0 END),
               SUM(CASE WHEN e.latitude IS NULL OR e.longitude IS NULL
                   THEN 1 ELSE 0 END)
        FROM discovery_entities e
        WHERE {active_sfa_filter}
        """,
        (SFA_SOURCE_ID,),
    )
    totals = cursor.fetchone()

    cursor.execute(
        f"""
        SELECT fp.venue_kind, COUNT(*)
        FROM discovery_entities e
        JOIN discovery_food_profiles fp ON fp.entity_id = e.id
        WHERE {active_sfa_filter}
        GROUP BY fp.venue_kind
        ORDER BY fp.venue_kind
        """,
        (SFA_SOURCE_ID,),
    )
    by_kind = {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    cursor.execute(
        f"""
        SELECT fs.safe_grade, COUNT(*)
        FROM discovery_entities e
        JOIN discovery_food_safety_profiles fs ON fs.entity_id = e.id
        WHERE {active_sfa_filter}
        GROUP BY fs.safe_grade
        ORDER BY fs.safe_grade
        """,
        (SFA_SOURCE_ID,),
    )
    by_grade = {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    cursor.execute(
        f"""
        SELECT COUNT(*),
               SUM(CASE WHEN e.latitude IS NOT NULL AND e.longitude IS NOT NULL
                   THEN 1 ELSE 0 END),
               SUM(CASE WHEN e.latitude IS NULL OR e.longitude IS NULL
                   THEN 1 ELSE 0 END)
        FROM discovery_source_records om
        JOIN discovery_entities e ON e.id = om.entity_id
        WHERE om.source_id = {p}
          AND e.status = 'active'
          AND EXISTS (
              SELECT 1 FROM discovery_source_records sfa
              WHERE sfa.source_id = {p} AND sfa.entity_id = e.id
          )
        """,
        (ONEMAP_FOOD_LOCATION_SOURCE_ID, SFA_SOURCE_ID),
    )
    one_map = cursor.fetchone()
    conn.close()

    return FoodCatalogReport(
        generated_at=generated_at,
        active_food_establishments=int(totals[0] or 0),
        establishments_by_kind=by_kind,
        establishments_by_safe_grade=by_grade,
        missing_postal_code=int(totals[1] or 0),
        missing_coordinates=int(totals[2] or 0),
        one_map_attempted=int(one_map[0] or 0),
        one_map_matched=int(one_map[1] or 0),
        one_map_rejected=int(one_map[2] or 0),
    )
