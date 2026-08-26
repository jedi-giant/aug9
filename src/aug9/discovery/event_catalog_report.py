from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aug9.core import database
from aug9.discovery.public_events import PUBLIC_EVENT_SOURCES


@dataclass(frozen=True)
class EventCatalogReport:
    generated_at: datetime
    active_upcoming_events: int
    events_by_source: dict[str, int]
    earliest_start: str | None
    latest_end: str | None
    missing_location: int
    missing_postal_code: int
    missing_coordinates: int
    missing_booking_url: int
    possible_duplicate_groups: int
    recent_failed_runs: int
    recent_rejected_records: int

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "active_upcoming_events": self.active_upcoming_events,
            "events_by_source": self.events_by_source,
            "coverage": {
                "earliest_start": self.earliest_start,
                "latest_end": self.latest_end,
            },
            "quality": {
                "missing_location": self.missing_location,
                "missing_postal_code": self.missing_postal_code,
                "missing_coordinates": self.missing_coordinates,
                "missing_booking_url": self.missing_booking_url,
                "possible_duplicate_groups": self.possible_duplicate_groups,
            },
            "ingestion_last_7_days": {
                "failed_runs": self.recent_failed_runs,
                "rejected_records": self.recent_rejected_records,
            },
        }


def build_event_catalog_report(
    *, now: datetime | None = None
) -> EventCatalogReport:
    generated_at = now or datetime.now(UTC)
    recent_cutoff = generated_at - timedelta(days=7)
    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    active_filter = (
        "e.status = 'active' AND e.entity_type = 'event' "
        f"AND COALESCE(ep.ends_at, ep.starts_at) >= {p}"
    )

    source_ids = [source.id for source in PUBLIC_EVENT_SOURCES]
    source_placeholders = ", ".join(p for _ in source_ids)
    cursor.execute(
        f"""
        SELECT ep.source_id, COUNT(*)
        FROM discovery_entities e
        JOIN discovery_event_profiles ep ON ep.entity_id = e.id
        WHERE {active_filter}
        GROUP BY ep.source_id
        ORDER BY ep.source_id
        """,
        (generated_at.isoformat(),),
    )
    events_by_source = {str(row[0]): int(row[1]) for row in cursor.fetchall()}

    cursor.execute(
        f"""
        SELECT COUNT(*), MIN(ep.starts_at), MAX(COALESCE(ep.ends_at, ep.starts_at)),
               SUM(CASE WHEN e.address IS NULL OR e.address = '' THEN 1 ELSE 0 END),
               SUM(CASE WHEN e.postal_code IS NULL OR e.postal_code = '' THEN 1 ELSE 0 END),
               SUM(CASE WHEN e.latitude IS NULL OR e.longitude IS NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN ep.booking_url IS NULL OR ep.booking_url = '' THEN 1 ELSE 0 END)
        FROM discovery_entities e
        JOIN discovery_event_profiles ep ON ep.entity_id = e.id
        WHERE {active_filter}
        """,
        (generated_at.isoformat(),),
    )
    totals = cursor.fetchone()

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT LOWER(e.name), ep.starts_at
            FROM discovery_entities e
            JOIN discovery_event_profiles ep ON ep.entity_id = e.id
            WHERE {active_filter}
            GROUP BY LOWER(e.name), ep.starts_at
            HAVING COUNT(*) > 1
        ) duplicates
        """,
        (generated_at.isoformat(),),
    )
    duplicate_groups = int(cursor.fetchone()[0])

    cursor.execute(
        f"""
        SELECT
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END),
            SUM(records_rejected)
        FROM discovery_ingestion_runs
        WHERE started_at >= {p}
          AND source_id IN ({source_placeholders})
        """,
        (recent_cutoff.isoformat(), *source_ids),
    )
    ingestion = cursor.fetchone()
    conn.close()

    return EventCatalogReport(
        generated_at=generated_at,
        active_upcoming_events=int(totals[0] or 0),
        events_by_source=events_by_source,
        earliest_start=str(totals[1]) if totals[1] is not None else None,
        latest_end=str(totals[2]) if totals[2] is not None else None,
        missing_location=int(totals[3] or 0),
        missing_postal_code=int(totals[4] or 0),
        missing_coordinates=int(totals[5] or 0),
        missing_booking_url=int(totals[6] or 0),
        possible_duplicate_groups=duplicate_groups,
        recent_failed_runs=int(ingestion[0] or 0),
        recent_rejected_records=int(ingestion[1] or 0),
    )
