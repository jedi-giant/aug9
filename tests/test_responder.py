from aug9.core.responder import compose_response
from aug9.core.executor import ExecutionResult
from aug9.core.planner import Plan
from aug9.models import (
    FoodResult,
    FoodRecommendation,
    WeatherResult,
    Weather,
    SearchStatus,
)
from aug9.core.models import Place
from aug9.core.skill import SkillResult


def test_response_combines_food_and_weather():

    plan = Plan(
        intent="food and weather",
        required_capabilities=[
            "food",
            "weather",
        ],
    )

    result = ExecutionResult(
        plan=plan,
        outputs={
            "food": FoodResult(
                status=SearchStatus.SUCCESS,
                recommendations=[
                    FoodRecommendation(
                        name="Tian Tian Chicken Rice",
                        description="Chicken rice",
                        place=Place(
                            name="Maxwell Food Centre",
                            place_type="hawker",
                            address="1 Kadayanallur Street",
                            postal_code="069184",
                            latitude=1.28,
                            longitude=103.84,
                        ),
                    )
                ],
            ),
            "weather": WeatherResult(
                status=SearchStatus.SUCCESS,
                weather=Weather(
                    forecast="Partly cloudy"
                ),
            ),
        },
    )

    response = compose_response(result)

    assert "Tian Tian Chicken Rice" in response
    assert "Partly cloudy" in response


def test_response_supports_registered_weather_skill_result():
    result = ExecutionResult(
        plan=Plan(intent="weather", required_capabilities=["weather"]),
        outputs={
            "weather": SkillResult(
                success=True,
                data={"weather": {"forecast": "Windy"}},
            )
        },
    )

    assert compose_response(result) == "Weather forecast: Windy."


def test_response_supports_registered_transport_skill_result():
    result = ExecutionResult(
        plan=Plan(intent="route", required_capabilities=["transport"]),
        outputs={
            "transport": SkillResult(
                success=True,
                data={
                    "route": {
                        "summary": "Walk from Maxwell Food Centre to Marina Bay Sands."
                    }
                },
            )
        },
    )

    assert compose_response(result) == (
        "Walk from Maxwell Food Centre to Marina Bay Sands."
    )
