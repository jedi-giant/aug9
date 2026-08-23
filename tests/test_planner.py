from aug9.core.planner import create_plan


def test_planner_identifies_food_and_weather():

    plan = create_plan(
        "Should I eat lunch outside today?"
    )

    assert "food" in plan.required_capabilities
