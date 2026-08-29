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


def test_response_surfaces_transport_failure_summary():
    result = ExecutionResult(
        plan=Plan(intent="route", required_capabilities=["transport"]),
        outputs={
            "transport": SkillResult(
                success=False,
                summary="Unable to resolve the route destination.",
            )
        },
    )

    assert compose_response(result) == "Unable to resolve the route destination."


def test_response_surfaces_place_and_weather_failure_summaries():
    result = ExecutionResult(
        plan=Plan(
            intent="weather",
            required_capabilities=["place_resolution", "weather"],
        ),
        outputs={
            "place_resolution": SkillResult(
                success=False,
                summary="Singapore place search is temporarily unavailable.",
            ),
            "weather": SkillResult(
                success=False,
                summary="Singapore weather information is temporarily unavailable.",
            ),
        },
    )

    response = compose_response(result)

    assert "place search is temporarily unavailable" in response
    assert "weather information is temporarily unavailable" in response


def test_response_supports_registered_hawker_skill_result():
    result = ExecutionResult(
        plan=Plan(intent="hawkers", required_capabilities=["hawkers"]),
        outputs={
            "hawkers": SkillResult(
                success=True,
                data={"places": [{"name": "Maxwell Food Centre"}]},
            )
        },
    )

    assert compose_response(result) == "Hawker centres: Maxwell Food Centre."


def test_response_preserves_distance_aware_hawker_summary():
    result = ExecutionResult(
        plan=Plan(intent="hawkers", required_capabilities=["hawkers"]),
        outputs={
            "hawkers": SkillResult(
                success=True,
                data={
                    "places": [
                        {"name": "Maxwell Food Centre", "distance_km": 0.8}
                    ]
                },
                summary=(
                    "Nearby hawker centres: Maxwell Food Centre "
                    "(0.8 km away; walking may be practical)."
                ),
            )
        },
    )

    assert compose_response(result) == (
        "Nearby hawker centres: Maxwell Food Centre "
        "(0.8 km away; walking may be practical)."
    )


def test_response_supports_registered_hotel_skill_result():
    result = ExecutionResult(
        plan=Plan(intent="hotels", required_capabilities=["hotels"]),
        outputs={
            "hotels": SkillResult(
                success=True,
                data={"places": [{"name": "Hotel Bencoolen"}]},
            )
        },
    )

    assert compose_response(result) == "Licensed hotels: Hotel Bencoolen."


def test_response_supports_registered_playground_skill_result():
    result = ExecutionResult(
        plan=Plan(intent="playgrounds", required_capabilities=["playgrounds"]),
        outputs={
            "playgrounds": SkillResult(
                success=True,
                data={"playgrounds": [{"name": "Neighbourhood Playground"}]},
                summary="Here are a few playgrounds to consider: Neighbourhood Playground.",
            )
        },
    )

    assert compose_response(result) == (
        "Here are a few playgrounds to consider: Neighbourhood Playground."
    )
