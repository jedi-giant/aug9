from unittest.mock import patch

from aug9.core.llm_planner import LLMPlan, PlanEntities
from aug9.core.planner_router import plan
from aug9.core.memory import ConversationState, JourneyState


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_llm_planner_is_supplemented_by_rule_transport_plan(mock_llm_plan):
    mock_llm_plan.return_value = LLMPlan(
        intent="route",
        required_capabilities=[],
        entities=PlanEntities(),
    )

    result = plan(
        "How do I get from Changi Airport to Pulau Ubin?"
    )

    assert "transport" in result.required_capabilities
    mock_llm_plan.assert_called_once()


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_rule_transport_intent_removes_incidental_llm_food(mock_llm_plan):
    mock_llm_plan.return_value = LLMPlan(
        intent="route",
        required_capabilities=["place_resolution", "food"],
        entities=PlanEntities(
            origin="Maxwell Food Centre",
            destination="Gardens by the Bay Flower Dome",
        ),
    )

    result = plan(
        "Give me public transport directions from Changi Airport "
        "to Pulau Ubin."
    )

    assert "transport" in result.required_capabilities
    assert "food" not in result.required_capabilities
    assert result.entities.travel_mode == "public_transport"


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_rule_weather_intent_removes_incidental_llm_food(mock_llm_plan):
    mock_llm_plan.return_value = LLMPlan(
        intent="weather",
        required_capabilities=["place_resolution", "weather", "food"],
        entities=PlanEntities(location="Maxwell Food Centre"),
    )

    result = plan("Could it rain around where I am staying?")

    assert "weather" in result.required_capabilities
    assert "food" not in result.required_capabilities


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_confident_weather_request_skips_llm_planner(mock_llm_plan):
    result = plan("What is the weather at Maxwell Food Centre?")

    assert "weather" in result.required_capabilities
    assert result.entities["location"] == "Maxwell Food Centre"
    mock_llm_plan.assert_not_called()


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_lifeops_request_keeps_llm_planner(mock_llm_plan):
    mock_llm_plan.return_value = LLMPlan(
        intent="plan day",
        required_capabilities=["events", "lifeops"],
        entities=PlanEntities(plan_type="day"),
    )

    plan("Plan my Saturday from Maxwell Food Centre")

    mock_llm_plan.assert_called_once()


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_short_location_reply_repairs_previous_food_request(mock_llm_plan):
    memory = ConversationState(
        last_intent="Find me a place to eat nearby",
        history=["Find me a place to eat nearby"],
    )

    result = plan("Punggol", memory)

    assert "food" in result.required_capabilities
    assert "place_resolution" in result.required_capabilities
    assert result.entities["location"] == "Punggol"
    assert "transport" not in result.required_capabilities
    mock_llm_plan.assert_not_called()


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_short_location_reply_continues_original_composite_journey(mock_llm_plan):
    original = "Help me plan a Singapore day out with food, weather and transport"
    memory = ConversationState(
        last_intent="Katong",
        history=[original, "Katong"],
        journey=JourneyState(
            journey_type="day",
            original_intent=original,
            requested_capabilities=["food", "weather", "transport", "lifeops"],
        ),
    )

    result = plan("Katong", memory)

    assert {"food", "weather", "transport", "lifeops"}.issubset(
        result.required_capabilities
    )
    assert result.entities["location"] == "Katong"
    assert result.entities["origin"] == "Katong"
    assert "destination" not in result.entities
    mock_llm_plan.assert_not_called()
