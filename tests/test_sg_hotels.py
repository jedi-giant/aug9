import sqlite3

from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.discovery.models import DiscoveryEntity, EntityType
from aug9.sg_hotels import DatabaseHotelProvider, SgHotelsSkill


class FakeRepository:
    def __init__(self, entities=None, error=None):
        self.entities = entities or []
        self.error = error
        self.calls = []

    def search_entities(self, query, *, entity_type, limit):
        self.calls.append((query, entity_type, limit))
        if self.error:
            raise self.error
        return self.entities


class FakeHotelProvider:
    def __init__(self):
        self.queries = []

    def discover(self, query=None):
        self.queries.append(query)
        return [
            Place(
                name="Hotel Bencoolen",
                place_type="hotel",
                postal_code="189626",
            )
        ]


def test_database_hotel_provider_returns_canonical_hotels():
    repository = FakeRepository(entities=[
        DiscoveryEntity(
            id="hotel:19844",
            entity_type=EntityType.HOTEL,
            name="Hotel Bencoolen",
            postal_code="189626",
            latitude=1.2991,
            longitude=103.8501,
            quality_score=1.0,
        )
    ])
    places = DatabaseHotelProvider(repository=repository).discover("Bencoolen")

    assert [place.name for place in places] == ["Hotel Bencoolen"]
    assert places[0].postal_code == "189626"
    assert repository.calls == [("Bencoolen", EntityType.HOTEL.value, 12)]


def test_database_hotel_provider_handles_database_failure():
    repository = FakeRepository(error=sqlite3.OperationalError("unavailable"))

    assert DatabaseHotelProvider(repository=repository).discover() == []


def test_sg_hotels_returns_structured_places_and_actions():
    result = SgHotelsSkill(FakeHotelProvider()).execute(UserContext(), {})

    assert result.success is True
    assert result.data["places"][0]["name"] == "Hotel Bencoolen"
    assert result.actions[0].metadata["capability"] == "hotels"


def test_sg_hotels_extracts_query_from_intent():
    provider = FakeHotelProvider()
    result = SgHotelsSkill(provider).execute(
        UserContext(intent="Find hotels near Bencoolen"),
        {},
    )

    assert result.success is True
    assert provider.queries == ["Bencoolen"]


def test_sg_hotels_keeps_broad_singapore_request_unfiltered():
    provider = FakeHotelProvider()

    SgHotelsSkill(provider).execute(
        UserContext(intent="Show me hotels in Singapore"),
        {},
    )

    assert provider.queries == [None]
