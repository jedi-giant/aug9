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
