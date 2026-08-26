from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.models import LocationSearchResult, SearchStatus
from aug9.sg_place.skill import SgPlaceSkill


class FakePlaceProvider:
    def __init__(self, result: LocationSearchResult) -> None:
        self.result = result
        self.queries: list[str] = []

    def search(self, query: str) -> LocationSearchResult:
        self.queries.append(query)
        return self.result


def test_sg_place_resolves_location_through_provider():
    place = Place(name="MAXWELL FOOD CENTRE", latitude=1.28, longitude=103.84)
    provider = FakePlaceProvider(
        LocationSearchResult(status=SearchStatus.SUCCESS, location=place)
    )

    result = SgPlaceSkill(provider).execute(
        UserContext(), {"location": "Maxwell Food Centre"}
    )

    assert result.success is True
    assert result.data["place"]["name"] == "MAXWELL FOOD CENTRE"
    assert provider.queries == ["Maxwell Food Centre"]


def test_sg_place_reuses_context_place_without_provider_call():
    place = Place(name="Maxwell Food Centre")
    provider = FakePlaceProvider(LocationSearchResult(status=SearchStatus.NO_RESULTS))

    result = SgPlaceSkill(provider).execute(UserContext(current_place=place), {})

    assert result.success is True
    assert result.data["place"]["name"] == "Maxwell Food Centre"
    assert provider.queries == []


def test_sg_place_reuses_matching_resolved_context_with_query():
    place = Place(name="MAXWELL FOOD CENTRE")
    provider = FakePlaceProvider(LocationSearchResult(status=SearchStatus.NO_RESULTS))

    result = SgPlaceSkill(provider).execute(
        UserContext(current_place=place), {"location": "Maxwell Food Centre"}
    )

    assert result.success is True
    assert provider.queries == []


def test_sg_place_preserves_provider_failure_message():
    provider = FakePlaceProvider(
        LocationSearchResult(
            status=SearchStatus.NETWORK_ERROR,
            message="OneMap unavailable",
        )
    )

    result = SgPlaceSkill(provider).execute(UserContext(), {"location": "Maxwell"})

    assert result.success is False
    assert result.summary == (
        "Singapore place search is temporarily unavailable. "
        "Please try again shortly."
    )
