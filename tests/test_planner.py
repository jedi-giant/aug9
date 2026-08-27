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


def test_planner_routes_nearby_food_through_hawkers_and_extracts_constraints():
    plan = create_plan("Find halal lunch near me under $15 that is open now")

    assert "food" in plan.required_capabilities
    assert "hawkers" in plan.required_capabilities
    assert plan.entities["budget_sgd"] == 15
    assert plan.entities["meal_type"] == "lunch"
    assert plan.entities["dietary_preferences"] == ["halal"]
    assert plan.entities["open_now"] is True


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


def test_planner_detects_expanded_government_service_request():
    plan = create_plan("How do I register my child's birth?")

    assert "services" in plan.required_capabilities


def test_planner_extracts_explicit_transport_mode():
    plan = create_plan("Can I cycle from Maxwell Food Centre to Marina Bay Sands?")

    assert "transport" in plan.required_capabilities
    assert plan.entities["travel_mode"] == "cycle"


def test_planner_treats_food_centre_as_a_transport_location():
    plan = create_plan(
        "Give me public transport directions from Maxwell Food Centre "
        "to Gardens by the Bay Flower Dome."
    )

    assert "transport" in plan.required_capabilities
    assert "food" not in plan.required_capabilities
    assert plan.entities["travel_mode"] == "public_transport"


def test_planner_treats_food_centre_as_a_weather_location():
    plan = create_plan("What is the weather at Maxwell Food Centre?")

    assert "weather" in plan.required_capabilities
    assert "food" not in plan.required_capabilities


def test_planner_preserves_explicit_food_request_with_weather():
    plan = create_plan(
        "What is the weather at Maxwell Food Centre and where should I eat?"
    )

    assert "weather" in plan.required_capabilities
    assert "food" in plan.required_capabilities
