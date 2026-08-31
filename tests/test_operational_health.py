from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.core.operational_health import build_operational_health_report
from aug9.discovery.public_events import PUBLIC_EVENT_SOURCES


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "health.db")
    database.initialise_database()
    for name in ("OPENAI_API_KEY", "ONEMAP_BASE_URL", "ONEMAP_EMAIL", "ONEMAP_PASSWORD"):
        monkeypatch.setenv(name, "configured")


def test_operational_health_reports_fresh_successful_daily_imports():
    now = datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
    conn = database.get_connection()
    cursor = conn.cursor()
    for index, source in enumerate(PUBLIC_EVENT_SOURCES):
        cursor.execute(
            """INSERT INTO discovery_sources
               (id, name, permission, active) VALUES (?, ?, 'legal_reviewed', 1)""",
            (source.id, source.name),
        )
        cursor.execute(
            """INSERT INTO discovery_ingestion_runs
               (id, source_id, status, started_at, completed_at)
               VALUES (?, ?, 'completed', ?, ?)""",
            (f"run-{index}", source.id, now.isoformat(), now.isoformat()),
        )
    conn.commit()
    conn.close()

    report = build_operational_health_report(now=now)

    assert report["healthy"] is True
    assert report["daily_imports"]["stale_sources"] == []


def test_operational_health_identifies_missing_runs():
    report = build_operational_health_report(
        now=datetime(2026, 8, 31, 2, 0, tzinfo=UTC)
    )

    assert report["healthy"] is False
    assert set(report["daily_imports"]["stale_sources"]) == {
        source.id for source in PUBLIC_EVENT_SOURCES
    }
