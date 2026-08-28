import pytest

from aug9.core import database
from aug9.core.models import Place
from aug9.discovery.food_locations import FoodLocationEnricher
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID
from aug9.models import LocationSearchResult, SearchStatus


class FakeOneMapProvider:
    def __init__(self, results, token="token"):
        self.results = results
        self.token = token
        self.queries = []

    def authenticate(self):
        return self.token

    def search_with_token(self, query, token):
        self.queries.append((query, token))
        return self.results[query]


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "food-locations.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA food establishments",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    for entity_id, name in (("food:1", "Stall One"), ("food:2", "Stall Two")):
        repository.upsert_entity(
            DiscoveryEntity(
                id=entity_id,
                entity_type=EntityType.FOOD_STALL,
                name=name,
                address="335 Smith Street Singapore 050335",
                postal_code="050335",
            ),
            SourceRecord(
                source_id=SFA_SOURCE_ID,
                external_id=entity_id,
                entity_id=entity_id,
            ),
            [],
        )
    return repository


def test_food_location_enrichment_reuses_one_postal_query(repository):
    provider = FakeOneMapProvider(
        {
            "050335": LocationSearchResult(
                status=SearchStatus.SUCCESS,
                location=Place(
                    name="Chinatown Complex",
                    address="335 Smith Street Singapore 050335",
                    postal_code="050335",
                    latitude=1.2823,
                    longitude=103.8431,
                ),
            )
        }
    )
    enricher = FoodLocationEnricher(
        repository,
        provider,
        request_delay_seconds=0,
    )

    summary = enricher.run()

    assert summary.received == 2
    assert summary.upserted == 2
    assert summary.unique_queries == 1
    assert provider.queries == [("050335", "token")]
    assert repository.get_entity("food:1").latitude == 1.2823
    assert repository.get_entity("food:2").longitude == 103.8431

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT entity_id, field_name FROM discovery_field_provenance "
        "WHERE source_id = 'onemap_food_locations' ORDER BY entity_id, field_name"
    )
    rows = cursor.fetchall()
    conn.close()
    assert len(rows) == 6


def test_food_location_rejection_is_recorded_and_not_retried(repository):
    provider = FakeOneMapProvider(
        {"050335": LocationSearchResult(status=SearchStatus.NO_RESULTS)}
    )
    enricher = FoodLocationEnricher(
        repository,
        provider,
        request_delay_seconds=0,
    )

    first = enricher.run()
    second = enricher.run()

    assert first.rejected == 2
    assert first.unique_queries == 1
    assert second.received == 0
    assert provider.queries == [("050335", "token")]


def test_food_location_rejects_postal_mismatch(repository):
    provider = FakeOneMapProvider(
        {
            "050335": LocationSearchResult(
                status=SearchStatus.SUCCESS,
                location=Place(
                    name="Wrong place",
                    postal_code="999999",
                    latitude=1.3,
                    longitude=103.8,
                ),
            )
        }
    )
    summary = FoodLocationEnricher(
        repository, provider, request_delay_seconds=0
    ).run()

    assert summary.upserted == 0
    assert summary.rejected == 2


def test_food_location_requires_authentication(repository):
    provider = FakeOneMapProvider({}, token=None)
    with pytest.raises(RuntimeError, match="authenticate"):
        FoodLocationEnricher(repository, provider).run()


def test_food_location_bounds_are_validated(repository):
    provider = FakeOneMapProvider({})
    with pytest.raises(ValueError, match="between 1 and 500"):
        FoodLocationEnricher(repository, provider, limit=501)
    with pytest.raises(ValueError, match="cannot be negative"):
        FoodLocationEnricher(repository, provider, request_delay_seconds=-0.1)
