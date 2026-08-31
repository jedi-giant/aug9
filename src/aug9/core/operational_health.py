import os
from datetime import UTC, datetime, timedelta

from aug9.core import database
from aug9.discovery.public_events import PUBLIC_EVENT_SOURCES


def build_operational_health_report(
    *, now: datetime | None = None, stale_after_hours: int = 36
) -> dict[str, object]:
    generated_at = now or datetime.now(UTC)
    providers = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "onemap": all(os.getenv(name) for name in (
            "ONEMAP_BASE_URL", "ONEMAP_EMAIL", "ONEMAP_PASSWORD"
        )),
        "nea_weather": True,
    }
    latest: dict[str, dict[str, object]] = {}
    database_ready = database.database_is_ready()
    if database_ready:
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT source_id, status, records_received, records_upserted,
                      records_rejected, error, started_at, completed_at
               FROM discovery_ingestion_runs ORDER BY started_at DESC"""
        )
        for row in cursor.fetchall():
            source_id = str(row[0])
            if source_id not in latest:
                latest[source_id] = {
                    "status": str(row[1]),
                    "received": int(row[2]),
                    "upserted": int(row[3]),
                    "rejected": int(row[4]),
                    "error": str(row[5]) if row[5] else None,
                    "started_at": str(row[6]),
                    "completed_at": str(row[7]) if row[7] else None,
                }
        conn.close()

    cutoff = generated_at - timedelta(hours=stale_after_hours)
    daily_source_ids = [source.id for source in PUBLIC_EVENT_SOURCES]
    stale_sources = []
    failed_sources = []
    for source_id in daily_source_ids:
        run = latest.get(source_id)
        if not run:
            stale_sources.append(source_id)
            continue
        if run["status"] == "failed":
            failed_sources.append(source_id)
        timestamp = _as_utc(run["completed_at"] or run["started_at"])
        if timestamp is None or timestamp < cutoff:
            stale_sources.append(source_id)

    healthy = (
        database_ready
        and all(providers.values())
        and not failed_sources
        and not stale_sources
    )
    return {
        "generated_at": generated_at.isoformat(),
        "healthy": healthy,
        "database": {"ready": database_ready},
        "providers": providers,
        "daily_imports": {
            "stale_after_hours": stale_after_hours,
            "stale_sources": stale_sources,
            "failed_sources": failed_sources,
            "latest_runs": {key: latest.get(key) for key in daily_source_ids},
        },
    }


def _as_utc(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
