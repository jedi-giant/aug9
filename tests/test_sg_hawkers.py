import sqlite3

from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.discovery.models import DiscoveryEntity, EntityType
from aug9.sg_hawkers.provider import (
    CuratedHawkerProvider,
    DatabaseHawkerProvider,
)
from aug9.sg_hawkers.skill import SgHawkersSkill


class FakeHawkerProvider:
    def __init__(self) -> None:
        self.queries: list[str | None] = []

    def discover(self, query: str | None = None) -> list[Place]:
        self.queries.append(query)
        return [Place(name="Maxwell Food Centre", place_type="hawker_centre")]

    def discover_near(self, latitude: float, longitude: float) -> list[Place]:
        self.queries.append(f"near:{latitude},{longitude}")
        return [
            Place(
                name="Maxwell Food Centre",
                place_type="hawker_centre",
                latitude=1.31,
                longitude=103.8519,
            )
        ]


class FakeDiscoveryRepository:
    def __init__(self, entities=None, error=None, results=None) -> None:
        self.entities = entities or []
        self.error = error
        self.results = results
        self.calls = []

    def search_entities(self, query, *, entity_type, limit):
        self.calls.append((query, entity_type, limit))
        if self.error:
            raise self.error
        if self.results is not None:
            return self.results.get(query, self.entities)
        return self.entities


def test_catalog_provider_loads_curated_hawker_centres():
    places = CuratedHawkerProvider().discover()

    assert len(places) == 8
    assert {place.name for place in places} >= {
        "Maxwell Food Centre",
        "Tiong Bahru Market",
        "Newton Food Centre",
    }
    assert all(place.latitude is not None for place in places)
    assert all(place.longitude is not None for place in places)


def test_catalog_provider_filters_by_location_name():
    places = CuratedHawkerProvider().discover("Newton")

    assert [place.name for place in places] == ["Newton Food Centre"]


def test_database_provider_returns_canonical_hawker_centres():
    repository = FakeDiscoveryRepository(
        entities=[
            DiscoveryEntity(
                id="hawker:123",
                entity_type=EntityType.HAWKER_CENTRE,
                name="Bishan Street 13 Hawker Centre",
                postal_code="570514",
                latitude=1.3509,
                longitude=103.8482,
                quality_score=1.0,
            )
        ]
    )
    provider = DatabaseHawkerProvider(repository=repository, limit=12)

    places = provider.discover("Bishan")

    assert [place.name for place in places] == [
        "Bishan Street 13 Hawker Centre"
    ]
    assert places[0].postal_code == "570514"
    assert repository.calls == [
        ("Bishan", EntityType.HAWKER_CENTRE.value, 12)
    ]


def test_database_provider_ranks_nearest_hawker_centres():
    repository = FakeDiscoveryRepository(
        entities=[
            DiscoveryEntity(
                id="hawker:far",
                entity_type=EntityType.HAWKER_CENTRE,
                name="Far Hawker Centre",
                latitude=1.35,
                longitude=103.90,
            ),
            DiscoveryEntity(
                id="hawker:near",
                entity_type=EntityType.HAWKER_CENTRE,
                name="Near Hawker Centre",
                latitude=1.291,
                longitude=103.852,
            ),
        ]
    )

    places = DatabaseHawkerProvider(repository=repository).discover_near(
        1.2903, 103.8519
    )

    assert [place.name for place in places] == [
        "Near Hawker Centre",
        "Far Hawker Centre",
    ]
    assert repository.calls == [(None, EntityType.HAWKER_CENTRE.value, 100)]


def test_database_provider_falls_back_when_database_is_unavailable():
    repository = FakeDiscoveryRepository(
        error=sqlite3.OperationalError("database unavailable")
    )
    fallback = FakeHawkerProvider()
    provider = DatabaseHawkerProvider(
        repository=repository,
        fallback=fallback,
    )

    places = provider.discover("Newton")

    assert [place.name for place in places] == ["Maxwell Food Centre"]
    assert fallback.queries == ["Newton"]


def test_database_provider_does_not_fall_back_for_unmatched_query():
    canonical = DiscoveryEntity(
        id="hawker:123",
        entity_type=EntityType.HAWKER_CENTRE,
        name="Adam Road Food Centre",
    )
    repository = FakeDiscoveryRepository(
        entities=[canonical],
        results={"Anchorvale Village": []},
    )
    fallback = FakeHawkerProvider()
    provider = DatabaseHawkerProvider(
        repository=repository,
        fallback=fallback,
    )

    places = provider.discover("Anchorvale Village")

    assert places == []
    assert fallback.queries == []
    assert repository.calls == [
        ("Anchorvale Village", EntityType.HAWKER_CENTRE.value, 12),
        (None, EntityType.HAWKER_CENTRE.value, 1),
    ]


def test_sg_hawkers_returns_structured_places():
    result = SgHawkersSkill(FakeHawkerProvider()).execute(UserContext(), {})

    assert result.success is True
    assert result.data["places"][0]["name"] == "Maxwell Food Centre"
    assert result.summary == "Nearby hawker centres: Maxwell Food Centre."
    assert result.actions[0].label == "Get directions to Maxwell Food Centre"
    assert "maps/dir/" in result.actions[0].url


def test_sg_hawkers_recovers_near_location_from_intent():
    provider = FakeHawkerProvider()

    result = SgHawkersSkill(provider).execute(
        UserContext(intent="Show me hawker centres near Newton"),
        {},
    )

    assert result.success is True
    assert provider.queries == ["Newton"]


def test_sg_hawkers_uses_coordinates_for_nearby_results():
    provider = FakeHawkerProvider()
    context = UserContext(
        intent="Find hawker centres near me",
        current_place=Place(
            name="Current location",
            latitude=1.2903,
            longitude=103.8519,
        ),
    )

    result = SgHawkersSkill(provider).execute(context, {})

    assert result.success is True
    assert provider.queries == ["near:1.2903,103.8519"]
    assert result.data["places"][0]["distance_km"] == 2.2
    assert "consider public transport" in result.summary
    assert "origin=" not in result.actions[0].url
    assert result.actions[0].metadata["distance_km"] == 2.2


def test_sg_hawkers_marks_unverified_constraint_evidence_as_unknown():
    result = SgHawkersSkill(FakeHawkerProvider()).execute(
        UserContext(),
        {
            "budget_sgd": 15,
            "meal_type": "lunch",
            "dietary_preferences": ["halal"],
            "open_now": True,
        },
    )

    place = result.data["places"][0]
    assert place["price_evidence"] == "unknown"
    assert place["opening_hours_evidence"] == "unknown"
    assert result.data["constraints"]["meal_type"] == "lunch"
    assert "Prices are not verified" in result.summary
    assert "Dietary suitability is not verified" in result.summary
    assert "Opening hours are not verified" in result.summary
