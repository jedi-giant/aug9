from aug9.core.executor import ExecutionResult
from aug9.core.planner import Plan
from aug9.core.responder import compose_response
from aug9.core.skill import SkillResult


def test_lifeops_uses_one_coordinated_location_question():
    execution = ExecutionResult(
        plan=Plan(
            intent="Plan my day",
            required_capabilities=["events", "food", "weather", "lifeops"],
        ),
        outputs={
            "events": SkillResult(success=False, summary="Share a place first."),
            "food": SkillResult(success=False, summary="Where are you starting?"),
            "weather": SkillResult(success=False, summary="Which area?"),
            "lifeops": SkillResult(
                success=True,
                data={"plan_type": "day", "location_available": False},
            ),
        },
    )

    response = compose_response(execution)

    assert response == (
        "Where are you starting from? Share a Singapore neighbourhood or place, "
        "and I'll plan nearby food, activities, weather and transport."
    )


def test_lifeops_preserves_itinerary_response_after_location_is_known():
    execution = ExecutionResult(
        plan=Plan(intent="Plan my day", required_capabilities=["events", "lifeops"]),
        outputs={
            "events": SkillResult(
                success=True,
                data={"events": [{"name": "Katong activity"}]},
            ),
            "lifeops": SkillResult(
                success=True,
                data={
                    "plan_type": "day",
                    "location_available": True,
                    "itinerary": [
                        {"type": "start", "title": "Start at Katong"},
                        {"type": "event", "title": "Katong activity"},
                    ],
                },
            ),
        },
    )

    response = compose_response(execution)

    assert response == (
        "Your Singapore day plan: Start at Katong. Then: Katong activity."
    )
