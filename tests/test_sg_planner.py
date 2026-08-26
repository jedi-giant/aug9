from aug9.core.context import UserContext
from aug9.core.executor import ExecutionResult
from aug9.core.planner import Plan, create_plan
from aug9.core.responder import compose_response
from aug9.core.skill import SkillResult
from aug9.sg_planner import SgPlannerSkill


def test_day_plan_requests_coordinate_existing_capabilities():
    plan = create_plan("Plan my Saturday in Singapore")

    assert {"events", "food", "weather", "lifeops"}.issubset(
        plan.required_capabilities
    )
    assert plan.entities["plan_type"] == "day"


def test_planner_skill_records_when_location_is_missing():
    result = SgPlannerSkill().execute(UserContext(intent="Plan my day"), {})

    assert result.success is True
    assert result.data["location_available"] is False


def test_lifeops_response_combines_outputs_and_requests_starting_area():
    execution = ExecutionResult(
        plan=Plan(intent="Plan my day", required_capabilities=["events", "lifeops"]),
        outputs={
            "events": SkillResult(
                success=True,
                data={"events": [{"name": "Night Festival"}]},
            ),
            "lifeops": SkillResult(
                success=True,
                data={"plan_type": "day", "location_available": False},
            ),
        },
    )

    response = compose_response(execution)

    assert response.startswith("Your Singapore day plan:")
    assert "Night Festival" in response
    assert "starting neighbourhood" in response
