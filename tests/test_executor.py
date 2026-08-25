from aug9.core.context import UserContext
from aug9.core.executor import CAPABILITIES, execute_plan
from aug9.core.planner import Plan
from aug9.core.models import Place
from aug9.core.skill_registry import SkillRegistry
from aug9.models import LocationSearchResult, SearchStatus, Weather, WeatherResult
from aug9.sg_place.skill import SgPlaceSkill


class FakePlaceProvider:
    def search(self, query: str) -> LocationSearchResult:
        return LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Place(name=query),
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

def test_executor_runs_weather_capability(monkeypatch):

    monkeypatch.setitem(
        CAPABILITIES,
        "weather",
        {
            "handler": lambda context, entities: WeatherResult(
                status=SearchStatus.SUCCESS,
                weather=Weather(forecast="Fair"),
            )
        },
    )

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
    )

    assert "weather" in result.outputs
    assert (
        result.outputs["weather"].status.value
        == "success"
    )

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
