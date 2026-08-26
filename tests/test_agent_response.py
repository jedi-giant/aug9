from aug9.core.agent_response import compose_agent_response
from aug9.core.executor import ExecutionResult
from aug9.core.planner import Plan
from aug9.core.skill import SkillAction, SkillResult


def test_agent_response_collects_actions_and_skill_metadata():
    execution = ExecutionResult(
        plan=Plan(intent="route", required_capabilities=["transport"]),
        outputs={
            "transport": SkillResult(
                success=True,
                data={"route": {"summary": "Walk to Marina Bay Sands."}},
                actions=[
                    SkillAction(
                        type="open_url",
                        label="Open directions",
                        url="https://example.com/directions",
                    )
                ],
            )
        },
    )

    result = compose_agent_response(execution)

    assert result.response == "Walk to Marina Bay Sands."
    assert result.actions[0].label == "Open directions"
    assert result.metadata["skills"]["transport"]["route"]["summary"] == (
        "Walk to Marina Bay Sands."
    )
    assert result.metadata["requested_capabilities"] == ["transport"]
    assert result.metadata["capability_outcomes"] == {"transport": "matched"}


def test_agent_response_records_unmatched_outcome_without_prompt_data():
    execution = ExecutionResult(
        plan=Plan(intent="unknown service", required_capabilities=["services"]),
        outputs={"services": SkillResult(success=False, summary="No match")},
    )

    result = compose_agent_response(execution)

    assert result.metadata["capability_outcomes"] == {"services": "unmatched"}
