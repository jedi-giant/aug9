from aug9.core.planner import create_plan


def test_planner_detects_multiple_capabilities():

    plan = create_plan(
        "Should I walk from Maxwell Food Centre to Marina Bay Sands and get lunch?"
    )

    assert "transport" in plan.required_capabilities
    assert "food" in plan.required_capabilities
