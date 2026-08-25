from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.sg_hawkers.provider import CuratedHawkerProvider
from aug9.sg_hawkers.skill import SgHawkersSkill


class FakeHawkerProvider:
    def __init__(self) -> None:
        self.queries: list[str | None] = []

    def discover(self, query: str | None = None) -> list[Place]:
        self.queries.append(query)
        return [Place(name="Maxwell Food Centre", place_type="hawker_centre")]


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


def test_sg_hawkers_returns_structured_places():
    result = SgHawkersSkill(FakeHawkerProvider()).execute(UserContext(), {})

    assert result.success is True
    assert result.data["places"][0]["name"] == "Maxwell Food Centre"
    assert result.summary == "Hawker centres: Maxwell Food Centre."


def test_sg_hawkers_recovers_near_location_from_intent():
    provider = FakeHawkerProvider()

    result = SgHawkersSkill(provider).execute(
        UserContext(intent="Show me hawker centres near Newton"),
        {},
    )

    assert result.success is True
    assert provider.queries == ["Newton"]
