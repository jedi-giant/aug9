from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.models import LocationSearchResult, Route, RouteResult, SearchStatus
from aug9.sg_transport.skill import SgTransportSkill
from aug9.sg_transport.provider import OneMapRouteProvider, OsrmRouteProvider
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
    assert result.data["recommended_mode"] == "public_transport"
    assert result.actions[0].label == "Open public transport directions"
    assert "travelmode=transit" in result.actions[0].url


def test_sg_transport_requires_both_places():
    result = SgTransportSkill(FakePlaceProvider(), FakeRouteProvider()).execute(
        UserContext(), {"destination": "Marina Bay Sands"}
    )

    assert result.success is False
    assert "Where are you starting from" in result.summary


def test_sg_transport_does_not_generate_a_route_to_the_same_place():
    result = SgTransportSkill(FakePlaceProvider(), FakeRouteProvider()).execute(
        UserContext(current_place=Place(name="Maxwell Food Centre")),
        {"destination": "Maxwell Food Centre"},
    )

    assert result.success is True
    assert result.data["recommended_mode"] == "none"
    assert result.data["route"]["duration_minutes"] == 0
    assert result.actions == []
    assert "already at" in result.summary


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


class ShortRouteProvider:
    def route(self, origin: Place, destination: Place) -> RouteResult:
        return RouteResult(
            status=SearchStatus.SUCCESS,
            route=Route(
                origin=origin.name,
                destination=destination.name,
                steps=[],
                summary="Short walk.",
                distance_meters=900,
                duration_minutes=12,
            ),
        )


class LongRouteProvider:
    def route(self, origin: Place, destination: Place) -> RouteResult:
        return RouteResult(
            status=SearchStatus.SUCCESS,
            route=Route(
                origin=origin.name,
                destination=destination.name,
                steps=[],
                summary="Long walk.",
                distance_meters=6200,
                duration_minutes=77.5,
            ),
        )


def test_short_route_remains_a_walking_recommendation():
    result = SgTransportSkill(FakePlaceProvider(), ShortRouteProvider()).execute(
        UserContext(),
        {
            "origin": "Maxwell Food Centre",
            "destination": "Marina Bay Sands",
            "travel_mode": "walk",
        },
    )

    assert result.data["recommended_mode"] == "walk"
    assert result.actions[0].label == "Open walking directions"
    assert "travelmode=walking" in result.actions[0].url


def test_long_route_recommends_transit_and_offers_taxi_alternative():
    result = SgTransportSkill(FakePlaceProvider(), LongRouteProvider()).execute(
        UserContext(),
        {"origin": "Maxwell Food Centre", "destination": "Marina Bay Sands"},
    )

    assert result.data["recommended_mode"] == "public_transport"
    assert "Public transport makes more sense" in result.summary
    assert [action.metadata["travel_mode"] for action in result.actions] == [
        "public_transport",
        "taxi_or_drive",
    ]


class FakeOneMap:
    base_url = "https://www.onemap.gov.sg"
    timeout = 10.0

    def authenticate(self):
        return "token"


@patch("aug9.sg_transport.provider.httpx.get")
def test_onemap_provider_parses_native_walking_route(mock_get):
    response = mock_get.return_value
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "route_summary": {"total_distance": 900, "total_time": 720},
        "route_instructions": [["Left", "Road", 0, "", 0, "", "", "", "", "Head left"]],
    }
    provider = OneMapRouteProvider(FakeOneMap())
    places = FakePlaceProvider()

    result = provider.route_for_mode(
        places.search("Maxwell Food Centre").location,
        places.search("Marina Bay Sands").location,
        "walk",
    )

    assert result.status == SearchStatus.SUCCESS
    assert result.route.duration_minutes == 12.0
    assert result.route.steps == ["Head left"]
    assert mock_get.call_args.kwargs["params"]["routeType"] == "walk"


@patch("aug9.sg_transport.provider.httpx.get")
def test_onemap_provider_parses_native_public_transport_route(mock_get):
    response = mock_get.return_value
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "plan": {
            "itineraries": [
                {
                    "duration": 1500,
                    "walkDistance": 450,
                    "legs": [
                        {
                            "mode": "SUBWAY",
                            "from": {"name": "Maxwell MRT"},
                            "to": {"name": "Orchard MRT"},
                            "distance": 5000,
                        }
                    ],
                }
            ]
        }
    }
    provider = OneMapRouteProvider(FakeOneMap())
    places = FakePlaceProvider()

    result = provider.route_for_mode(
        places.search("Maxwell Food Centre").location,
        places.search("Marina Bay Sands").location,
        "public_transport",
    )

    assert result.status == SearchStatus.SUCCESS
    assert result.route.duration_minutes == 25.0
    assert result.route.steps == ["Subway: Maxwell MRT to Orchard MRT"]
    params = mock_get.call_args.kwargs["params"]
    assert params["routeType"] == "pt"
    assert params["mode"] == "TRANSIT"


@patch("aug9.sg_transport.provider.httpx.get")
def test_onemap_provider_rejects_walking_only_transit_result(mock_get):
    response = mock_get.return_value
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "plan": {
            "itineraries": [
                {
                    "duration": 2400,
                    "walkDistance": 3300,
                    "legs": [
                        {
                            "mode": "WALK",
                            "from": {"name": "Origin"},
                            "to": {"name": "Destination"},
                        }
                    ],
                }
            ]
        }
    }
    provider = OneMapRouteProvider(FakeOneMap())
    places = FakePlaceProvider()

    result = provider.route_for_mode(
        places.search("Maxwell Food Centre").location,
        places.search("Marina Bay Sands").location,
        "public_transport",
    )

    assert result.status == SearchStatus.API_ERROR
    assert result.route is None


class ModeAwareRouteProvider:
    def __init__(self):
        self.mode = None

    def route_for_mode(self, origin, destination, mode):
        self.mode = mode
        return ShortRouteProvider().route(origin, destination)

    def route(self, origin, destination):
        return ShortRouteProvider().route(origin, destination)


def test_explicit_cycling_request_uses_native_cycle_mode():
    provider = ModeAwareRouteProvider()
    result = SgTransportSkill(FakePlaceProvider(), provider).execute(
        UserContext(intent="Can I cycle there?"),
        {
            "origin": "Maxwell Food Centre",
            "destination": "Marina Bay Sands",
            "travel_mode": "cycle",
        },
    )

    assert provider.mode == "cycle"
    assert result.data["recommended_mode"] == "cycle"
    assert "travelmode=bicycling" in result.actions[0].url


class WalkingOnlyTransitProvider:
    def route_for_mode(self, origin, destination, mode):
        return RouteResult(
            status=SearchStatus.API_ERROR,
            message="OneMap returned no public transport leg",
        )

    def route(self, origin, destination):
        return RouteResult(
            status=SearchStatus.SUCCESS,
            route=Route(
                origin=origin.name,
                destination=destination.name,
                steps=["Walk-only fallback step"],
                summary=f"Walk from {origin.name} to {destination.name}.",
                distance_meters=3302,
                duration_minutes=39.6,
            ),
        )


def test_transit_fallback_does_not_surface_walking_summary():
    result = SgTransportSkill(
        FakePlaceProvider(), WalkingOnlyTransitProvider()
    ).execute(
        UserContext(intent="Give me public transport directions."),
        {
            "origin": "Maxwell Food Centre",
            "destination": "Marina Bay Sands",
            "travel_mode": "public_transport",
        },
    )

    assert result.data["recommended_mode"] == "public_transport"
    assert result.summary == (
        "Maxwell Food Centre to Marina Bay Sands is about 3.3 km. "
        "Public transport makes more sense — open the directions below "
        "for the latest options."
    )
    assert not result.summary.startswith("Walk from")
    assert "travelmode=transit" in result.actions[0].url
