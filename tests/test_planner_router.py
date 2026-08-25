from unittest.mock import patch

from aug9.core.llm_planner import LLMPlan, PlanEntities
from aug9.core.planner_router import plan


@patch("aug9.core.planner_router.PLANNER_MODE", "llm")
@patch("aug9.core.planner_router.create_llm_plan")
def test_llm_planner_is_supplemented_by_rule_transport_plan(mock_llm_plan):
    mock_llm_plan.return_value = LLMPlan(
        intent="route",
        required_capabilities=[],
        entities=PlanEntities(),
    )

    result = plan(
        "How do I get from Maxwell Food Centre to Marina Bay Sands?"
    )

    assert "transport" in result.required_capabilities
    assert result.entities.origin == "Maxwell Food Centre"
    assert result.entities.destination == "Marina Bay Sands"
