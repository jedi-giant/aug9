import pytest

from aug9.core import database
from aug9.core.models import Place
from aug9.discovery.event_venues import EventVenueEnricher
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.models import LocationSearchResult, SearchStatus


class FakeOneMapProvider:
    def __init__(self, result):
        self.result = result
        self.queries = []

    def authenticate(self):
        return "token"

    def search_with_token(self, query, token):
        self.queries.append((query, token))
        return self.result


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "events.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id="event_source",
            name="Event source",
            permission=SourcePermission.LEGAL_REVIEWED,
        )
    )
    for entity_id, address in (
        ("event:venue", "RELC International Hotel, 30 Orange Grove Road"),
        ("event:generic", "Various Locations"),
    ):
        repository.upsert_entity(
            DiscoveryEntity(
                id=entity_id,
                entity_type=EntityType.EVENT,
                name=entity_id,
                address=address,
            ),
            SourceRecord(
                source_id="event_source",
                external_id=entity_id,
                entity_id=entity_id,
            ),
            [],
        )
    return repository


def test_event_venue_enrichment_stores_coordinates_and_provenance(repository):
    provider = FakeOneMapProvider(
        LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Place(
                name="RELC INTERNATIONAL HOTEL",
                address="30 ORANGE GROVE ROAD SINGAPORE 258352",
                postal_code="258352",
                latitude=1.311,
                longitude=103.825,
            ),
        )
    )

    summary = EventVenueEnricher(repository, provider).run()
    entity = repository.get_entity("event:venue")

    assert summary.received == 1
    assert summary.upserted == 1
    assert entity.postal_code == "258352"
    assert entity.latitude == 1.311
    assert entity.longitude == 103.825
    assert provider.queries == [
        ("RELC International Hotel, 30 Orange Grove Road", "token")
    ]

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT field_name FROM discovery_field_provenance "
        "WHERE entity_id = ? ORDER BY field_name",
        ("event:venue",),
    )
    assert [row[0] for row in cursor.fetchall()] == [
        "latitude",
        "longitude",
        "postal_code",
    ]
    conn.close()


def test_event_venue_enrichment_skips_generic_locations(repository):
    candidates = EventVenueEnricher(
        repository,
        FakeOneMapProvider(LocationSearchResult(status=SearchStatus.NO_RESULTS)),
    ).get_candidates()

    assert [candidate.entity_id for candidate in candidates] == ["event:venue"]
