from aug9.core.context import UserContext
from aug9.core.executor import ExecutionResult
from aug9.core.journey import build_journey_state
from aug9.core.memory import ConversationState
from aug9.core.models import Place
from aug9.core.planner import Plan
from aug9.core.skill import SkillResult


def test_journey_state_records_origin_and_selected_stops():
    plan = Plan(
        intent="Plan a Singapore day out with food, weather and transport",
        required_capabilities=["food", "weather", "transport", "lifeops"],
        entities={"plan_type": "day"},
    )
    execution = ExecutionResult(
        plan=plan,
        outputs={
            "lifeops": SkillResult(
                success=True,
                data={
                    "itinerary": [
                        {"type": "start", "location": "Katong"},
                        {"type": "food", "location": "51 East Coast Road"},
                    ]
                },
            )
        },
    )

    state = build_journey_state(
        ConversationState(),
        plan,
        UserContext(current_place=Place(name="Katong")),
        execution,
    )

    assert state is not None
    assert state.original_intent == plan.intent
    assert state.resolved_slots["origin"]["name"] == "Katong"
    assert state.pending_slots == []
    assert state.status == "ready"


def test_journey_state_keeps_original_goal_while_clarifying():
    plan = Plan(
        intent="Plan my day",
        required_capabilities=["food", "weather", "lifeops"],
        entities={"plan_type": "day"},
    )
    state = build_journey_state(
        ConversationState(),
        plan,
        UserContext(),
        ExecutionResult(
            plan=plan,
            outputs={
                "lifeops": SkillResult(
                    success=True,
                    data={"itinerary": []},
                )
            },
        ),
    )

    assert state is not None
    assert state.pending_slots == ["origin"]
    assert state.status == "clarifying"
