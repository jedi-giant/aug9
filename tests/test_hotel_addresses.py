import pytest

from aug9.core import database
from aug9.core.models import Place
from aug9.discovery.hotel_addresses import HotelAddressEnricher
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
    def __init__(self, result, token="token"):
        self.result = result
        self.token = token
        self.queries = []

    def authenticate(self):
        return self.token

    def search_with_token(self, query, token):
        self.queries.append((query, token))
        return self.result


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "addresses.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id="hlb",
            name="Hotels Licensing Board",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    repository.upsert_entity(
        DiscoveryEntity(
            id="hotel:1",
            entity_type=EntityType.HOTEL,
            name="Example Hotel",
            postal_code="189626",
        ),
        SourceRecord(source_id="hlb", external_id="1", entity_id="hotel:1"),
        [],
    )
    return repository


def test_hotel_address_enricher_updates_address_with_provenance(repository):
    provider = FakeOneMapProvider(
        LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Place(
                name="189626",
                place_type="location",
                address="47 Bencoolen Street",
                postal_code="189626",
                latitude=1.299,
                longitude=103.85,
            ),
        )
    )
    summary = HotelAddressEnricher(repository, provider).run()

    stored = repository.get_entity("hotel:1")
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source_id, field_name FROM discovery_field_provenance "
        "WHERE entity_id = ?",
        ("hotel:1",),
    )
    provenance = cursor.fetchone()
    conn.close()

    assert summary.received == 1
    assert summary.upserted == 1
    assert summary.rejected == 0
    assert stored.address == "47 Bencoolen Street"
    assert provenance == ("onemap_hotel_addresses", "address")
    assert provider.queries == [("189626", "token")]


def test_hotel_address_enricher_rejects_postal_mismatch(repository):
    provider = FakeOneMapProvider(
        LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Place(
                name="Wrong result",
                place_type="location",
                address="Wrong address",
                postal_code="000000",
            ),
        )
    )
    summary = HotelAddressEnricher(repository, provider).run()

    assert summary.received == 1
    assert summary.upserted == 0
    assert summary.rejected == 1
    assert repository.get_entity("hotel:1").address is None


def test_hotel_address_enricher_requires_onemap_authentication(repository):
    provider = FakeOneMapProvider(
        LocationSearchResult(status=SearchStatus.NO_RESULTS),
        token=None,
    )

    with pytest.raises(RuntimeError, match="authenticate"):
        HotelAddressEnricher(repository, provider).run()
