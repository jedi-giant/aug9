from datetime import UTC, datetime, timedelta

import pytest

from aug9.core import database
from aug9.discovery.aggregation import (
    AggregationRecord,
    DataAggregationEngine,
    GeoResolution,
)
from aug9.discovery.models import DiscoverySource, EntityType, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


class Adapter:
    def __init__(self, records):
        self.records = records

    def collect(self):
        return self.records

    def parse(self, raw):
        return raw


class Geocoder:
    def resolve(self, address):
        return GeoResolution(
            address="1 Example Road",
            postal_code="123456",
            latitude=1.3,
            longitude=103.8,
        )


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "aggregation.db")
    database.initialise_database()
    return DiscoveryRepository()


def source(permission=SourcePermission.OPEN_DATA):
    return DiscoverySource(
        id="approved_feed",
        name="Approved feed",
        permission=permission,
        base_url="https://example.org",
        attribution="Example",
    )


def test_pipeline_geocodes_normalises_and_upserts(repository):
    record = AggregationRecord(
        external_id=" item-1 ",
        entity_type=EntityType.ACTIVITY,
        name="  Example   Activity ",
        address="Example Road",
        source_url="https://example.org/item-1",
        raw_facts={"name": "Example Activity"},
    )

    summary = DataAggregationEngine(repository, geocoder=Geocoder()).run(
        source(), Adapter([record])
    )
    matches = repository.search_entities("Example Activity")

    assert (summary.received, summary.upserted, summary.rejected) == (1, 1, 0)
    assert matches[0].postal_code == "123456"
    assert matches[0].latitude == 1.3


def test_fingerprint_deduplicates_equivalent_records():
    location = GeoResolution(address="1 Example Road", postal_code="123456")

    first = DataAggregationEngine.canonical_id(
        EntityType.FOOD_VENUE, "Cafe Example", location
    )
    second = DataAggregationEngine.canonical_id(
        EntityType.FOOD_VENUE, " cafe-example ", location
    )

    assert first == second


def test_recurring_events_on_different_days_remain_distinct():
    location = GeoResolution(address="Singapore")
    first = DataAggregationEngine.canonical_id(
        EntityType.EVENT,
        "Night Market",
        location,
        occurrence_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    second = DataAggregationEngine.canonical_id(
        EntityType.EVENT,
        "Night Market",
        location,
        occurrence_at=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert first != second


def test_link_only_source_cannot_enter_canonical_store(repository):
    record = AggregationRecord(
        external_id="article-1",
        entity_type=EntityType.ACTIVITY,
        name="Editorial idea",
    )

    with pytest.raises(ValueError, match="does not allow ingestion"):
        DataAggregationEngine(repository).run(
            source(SourcePermission.LINK_ONLY), Adapter([record])
        )


def test_expired_events_are_archived(repository):
    now = datetime(2026, 8, 26, tzinfo=UTC)
    record = AggregationRecord(
        external_id="event-1",
        entity_type=EntityType.EVENT,
        name="Finished Event",
        source_url="https://example.org/event-1",
        starts_at=now - timedelta(days=2),
        ends_at=now - timedelta(days=1),
    )
    DataAggregationEngine(repository, now=now).run(source(), Adapter([record]))

    assert repository.archive_expired_events(now=now) == 1
    entity_id = DataAggregationEngine.canonical_id(
        EntityType.EVENT,
        "Finished Event",
        GeoResolution(address="Singapore"),
        occurrence_at=record.starts_at,
    )
    assert repository.get_entity(entity_id).status == "archived"


@pytest.mark.parametrize(
    "source_id", ["eventbrite_api", "today_do_what", "ticketmaster_public"]
)
def test_schema_initialisation_archives_retired_entities(repository, source_id):
    retired = DiscoverySource(
        id=source_id,
        name="Retired source",
        permission=SourcePermission.LICENSED_PARTNER,
        base_url="https://example.org",
    )
    record = AggregationRecord(
        external_id="legacy-event",
        entity_type=EntityType.EVENT,
        name="Legacy Event",
        source_url="https://example.org/legacy-event",
        starts_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    engine = DataAggregationEngine(repository)
    engine.run(retired, Adapter([record]))
    entity_id = DataAggregationEngine.canonical_id(
        EntityType.EVENT,
        "Legacy Event",
        GeoResolution(address="Singapore"),
        occurrence_at=record.starts_at,
    )

    database.initialise_database()

    assert repository.get_entity(entity_id).status == "archived"
