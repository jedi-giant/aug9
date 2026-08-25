from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.sg_hawkers.provider import FoodCatalogHawkerProvider
from aug9.sg_hawkers.skill import SgHawkersSkill


class FakeHawkerProvider:
    def discover(self, query: str | None = None) -> list[Place]:
        return [Place(name="Maxwell Food Centre", place_type="hawker_centre")]


def test_catalog_provider_deduplicates_hawker_centres():
    places = FoodCatalogHawkerProvider().discover()

    assert [place.name for place in places] == ["Maxwell Food Centre"]


def test_sg_hawkers_returns_structured_places():
    result = SgHawkersSkill(FakeHawkerProvider()).execute(UserContext(), {})

    assert result.success is True
    assert result.data["places"][0]["name"] == "Maxwell Food Centre"
    assert result.summary == "Hawker centres: Maxwell Food Centre."
