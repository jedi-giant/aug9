from aug9.core.context import UserContext
from aug9.core.executor import execute_plan
from aug9.core.planner import Plan
from aug9.core.models import Place
from aug9.core.skill_registry import SkillRegistry
from aug9.models import LocationSearchResult, SearchStatus, Weather, WeatherResult
from aug9.sg_place.skill import SgPlaceSkill
from aug9.sg_weather.skill import SgWeatherSkill
from aug9.sg_transport.skill import SgTransportSkill
from aug9.sg_services import OfficialGovernmentServiceProvider, SgServicesSkill


class FakePlaceProvider:
    def search(self, query: str) -> LocationSearchResult:
        return LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Place(name=query),
        )


class FakeWeatherProvider:
    def forecast(self, place: Place) -> WeatherResult:
        return WeatherResult(
            status=SearchStatus.SUCCESS,
            weather=Weather(forecast="Fair"),
        )


class FakeRouteProvider:
    def route(self, origin: Place, destination: Place):
        from aug9.models import Route, RouteResult

        return RouteResult(
            status=SearchStatus.SUCCESS,
            route=Route(
                origin=origin.name,
                destination=destination.name,
                steps=["Bayfront Avenue"],
                summary=f"Walk from {origin.name} to {destination.name}.",
            ),
        )


def test_executor_routes_place_resolution_through_registry():
    registry = SkillRegistry()
    registry.register(SgPlaceSkill(FakePlaceProvider()))
    plan = Plan(
        intent="Find Maxwell",
        required_capabilities=["place_resolution"],
        entities={"location": "Maxwell Food Centre"},
    )

    result = execute_plan(plan, UserContext(), registry=registry)

    assert result.outputs["place_resolution"].success is True
    assert (
        result.outputs["place_resolution"].data["place"]["name"]
        == "Maxwell Food Centre"
    )

def test_executor_runs_weather_capability():
    registry = SkillRegistry()
    registry.register(SgWeatherSkill(FakeWeatherProvider()))

    plan = Plan(
        intent="Check weather at Maxwell",
        required_capabilities=[
            "weather",
        ],
    )

    context = UserContext(
        current_place=Place(
            name="Maxwell Food Centre",
            place_type="hawker_centre",
            address="1 Kadayanallur Street",
            postal_code="069184",
            latitude=1.280331,
            longitude=103.844747,
        )
    )

    result = execute_plan(
        plan,
        context,
        registry=registry,
    )

    assert "weather" in result.outputs
    assert result.outputs["weather"].success is True
    assert result.outputs["weather"].data["weather"]["forecast"] == "Fair"

def test_executor_runs_food_capability():

    plan = Plan(
        intent="Find food near Maxwell",
        required_capabilities=[
            "food",
        ],
    )

    context = UserContext(
        current_place=Place(
            name="Maxwell Food Centre",
            place_type="hawker_centre",
            address="1 Kadayanallur Street",
            postal_code="069184",
            latitude=1.280331,
            longitude=103.844747,
        )
    )

    result = execute_plan(
        plan,
        context,
    )

    assert "food" in result.outputs
    assert (
        result.outputs["food"].status.value
        == "success"
    )


def test_executor_routes_transport_through_registry():
    registry = SkillRegistry()
    registry.register(SgTransportSkill(FakePlaceProvider(), FakeRouteProvider()))
    plan = Plan(
        intent="Get from Maxwell to Marina Bay Sands",
        required_capabilities=["transport"],
        entities={
            "origin": "Maxwell Food Centre",
            "destination": "Marina Bay Sands",
        },
    )

    result = execute_plan(plan, UserContext(), registry=registry)

    assert result.outputs["transport"].success is True


def test_executor_routes_services_through_registry():
    registry = SkillRegistry()
    registry.register(SgServicesSkill(OfficialGovernmentServiceProvider()))
    plan = Plan(
        intent="Help me renew my passport",
        required_capabilities=["services"],
        entities={"service_query": "renew passport"},
    )

    result = execute_plan(plan, UserContext(), registry=registry)

    assert result.outputs["services"].success is True
    assert result.outputs["services"].actions[0].metadata["capability"] == "services"
