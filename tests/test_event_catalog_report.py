from datetime import UTC, datetime, timedelta

import pytest

from aug9.core import database
from aug9.discovery.aggregation import AggregationRecord, DataAggregationEngine
from aug9.discovery.event_catalog_report import build_event_catalog_report
from aug9.discovery.models import DiscoverySource, EntityType, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


class Adapter:
    def __init__(self, records):
        self.records = records

    def collect(self):
        return self.records

    def parse(self, raw):
        return raw


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "event-report.db")
    database.initialise_database()
    return DiscoveryRepository()


def test_event_catalog_report_summarises_coverage_and_quality(repository):
    now = datetime(2026, 8, 26, tzinfo=UTC)
    source = DiscoverySource(
        id="eventbrite_public",
        name="Event source",
        permission=SourcePermission.LEGAL_REVIEWED,
        base_url="https://events.example",
    )
    event = AggregationRecord(
        external_id="event-1",
        entity_type=EntityType.EVENT,
        name="Future Festival",
        address="Singapore",
        source_url="https://events.example/festival",
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=3),
        booking_url="https://events.example/festival",
    )
    DataAggregationEngine(repository, now=now).run(source, Adapter([event]))
    rejected_run = repository.start_ingestion(source.id)
    repository.complete_ingestion(
        rejected_run,
        records_received=2,
        records_upserted=0,
        records_rejected=2,
        error="ValueError",
    )

    report = build_event_catalog_report(now=now)

    assert report.active_upcoming_events == 1
    assert report.events_by_source == {"eventbrite_public": 1}
    assert report.missing_location == 0
    assert report.missing_postal_code == 1
    assert report.missing_booking_url == 0
    assert report.recent_failed_runs == 1
    assert report.recent_rejected_records == 2
