from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.models import LocationSearchResult, Route, RouteResult, SearchStatus
from aug9.sg_transport.skill import SgTransportSkill
from aug9.sg_transport.provider import OsrmRouteProvider
from unittest.mock import patch
import httpx


class FakePlaceProvider:
    def search(self, query: str) -> LocationSearchResult:
        places = {
            "Maxwell Food Centre": Place(
                name="Maxwell Food Centre", latitude=1.28, longitude=103.84
            ),
            "Marina Bay Sands": Place(
                name="Marina Bay Sands", latitude=1.283, longitude=103.859
            ),
        }
        place = places.get(query)
        return LocationSearchResult(
            status=SearchStatus.SUCCESS if place else SearchStatus.NO_RESULTS,
            location=place,
        )


class FakeRouteProvider:
    def route(self, origin: Place, destination: Place) -> RouteResult:
        return RouteResult(
            status=SearchStatus.SUCCESS,
            route=Route(
                origin=origin.name,
                destination=destination.name,
                steps=["South Bridge Road", "Bayfront Avenue"],
                summary=f"Walk from {origin.name} to {destination.name}.",
                distance_meters=1800,
                duration_minutes=24,
            ),
        )


def test_sg_transport_resolves_places_and_returns_route():
    result = SgTransportSkill(FakePlaceProvider(), FakeRouteProvider()).execute(
        UserContext(),
        {
            "origin": "Maxwell Food Centre",
            "destination": "Marina Bay Sands",
        },
    )

    assert result.success is True
    assert result.data["route"]["destination"] == "Marina Bay Sands"
    assert result.data["route"]["duration_minutes"] == 24


def test_sg_transport_requires_both_places():
    result = SgTransportSkill(FakePlaceProvider(), FakeRouteProvider()).execute(
        UserContext(), {"destination": "Marina Bay Sands"}
    )

    assert result.success is False
    assert result.summary == "Both origin and destination are required."


def test_sg_transport_recovers_endpoints_from_intent():
    result = SgTransportSkill(FakePlaceProvider(), FakeRouteProvider()).execute(
        UserContext(
            intent="How do I get from Maxwell Food Centre to Marina Bay Sands?"
        ),
        {},
    )

    assert result.success is True
    assert result.data["route"]["origin"] == "Maxwell Food Centre"
    assert result.data["route"]["destination"] == "Marina Bay Sands"


@patch("aug9.sg_transport.provider.calculate_route")
def test_osrm_provider_contains_network_errors(mock_calculate_route):
    mock_calculate_route.side_effect = httpx.RequestError("OSRM unavailable")

    result = OsrmRouteProvider().route(
        Place(name="Maxwell", latitude=1.28, longitude=103.84),
        Place(name="MBS", latitude=1.283, longitude=103.859),
    )

    assert result.status == SearchStatus.NETWORK_ERROR
    assert result.message == "OSRM unavailable"
