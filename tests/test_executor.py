from aug9.core.context import UserContext
from aug9.core.executor import execute_plan
from aug9.core.planner import Plan
from aug9.core.models import Place

def test_executor_runs_weather_capability():

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
