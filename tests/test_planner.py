from aug9.core.planner import create_plan

def test_planner_detects_place_resolution():

    plan = create_plan(
        "What is the weather at Maxwell Food Centre?"
    )

    assert "place_resolution" in plan.required_capabilities
    assert "weather" in plan.required_capabilities

def test_planner_identifies_food_and_weather():

    plan = create_plan(
        "Should I eat lunch outside today?"
    )

    assert "food" in plan.required_capabilities


def test_planner_detects_hawker_discovery():
    plan = create_plan("Show me hawker centres in Singapore")

    assert "hawkers" in plan.required_capabilities


def test_planner_detects_hotel_discovery():
    plan = create_plan("Show me hotels in Singapore")

    assert "hotels" in plan.required_capabilities


def test_planner_detects_event_discovery():
    plan = create_plan("What events are happening this weekend?")

    assert "events" in plan.required_capabilities


def test_planner_detects_government_service_request():
    plan = create_plan("How do I renew my Singapore passport?")

    assert "services" in plan.required_capabilities
    assert plan.entities["service_query"] == "How do I renew my Singapore passport?"
