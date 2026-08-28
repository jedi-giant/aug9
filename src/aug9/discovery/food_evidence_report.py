from dataclasses import dataclass
from datetime import UTC, datetime

from aug9.core import database


@dataclass(frozen=True)
class FoodEvidenceReport:
    generated_at: datetime
    total_records: int
    active_records: int
    expired_records: int
    covered_entities: int
    dish_specific_records: int
    records_by_dimension: dict[str, int]
    records_by_type: dict[str, int]
    records_by_commercial_status: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_records": self.total_records,
            "active_records": self.active_records,
            "expired_records": self.expired_records,
            "covered_entities": self.covered_entities,
            "dish_specific_records": self.dish_specific_records,
            "records_by_dimension": self.records_by_dimension,
            "records_by_type": self.records_by_type,
            "records_by_commercial_status": self.records_by_commercial_status,
        }


def build_food_evidence_report(
    *, now: datetime | None = None
) -> FoodEvidenceReport:
    generated_at = now or datetime.now(UTC)
    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    cursor.execute(
        f"""
        SELECT COUNT(*),
               SUM(CASE WHEN expires_at IS NULL OR expires_at >= {p}
                   THEN 1 ELSE 0 END),
               SUM(CASE WHEN expires_at < {p} THEN 1 ELSE 0 END),
               COUNT(DISTINCT entity_id),
               SUM(CASE WHEN dish_name IS NOT NULL AND dish_name != ''
                   THEN 1 ELSE 0 END)
        FROM discovery_food_evidence
        """,
        (generated_at.isoformat(), generated_at.isoformat()),
    )
    totals = cursor.fetchone()

    def grouped(column: str) -> dict[str, int]:
        cursor.execute(
            f"""
            SELECT {column}, COUNT(*)
            FROM discovery_food_evidence
            GROUP BY {column}
            ORDER BY {column}
            """
        )
        return {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    by_dimension = grouped("dimension")
    by_type = grouped("evidence_type")
    by_commercial_status = grouped("commercial_status")
    conn.close()
    return FoodEvidenceReport(
        generated_at=generated_at,
        total_records=int(totals[0] or 0),
        active_records=int(totals[1] or 0),
        expired_records=int(totals[2] or 0),
        covered_entities=int(totals[3] or 0),
        dish_specific_records=int(totals[4] or 0),
        records_by_dimension=by_dimension,
        records_by_type=by_type,
        records_by_commercial_status=by_commercial_status,
    )
