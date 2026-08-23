from unittest.mock import patch

from aug9.core.planner_agent import (
    create_llm_plan,
)

from aug9.core.llm_planner import (
    LLMPlan,
    PlanEntities,
)


@patch("aug9.core.planner_agent.client")
def test_llm_planner_returns_plan(
    mock_client,
):

    mock_client.responses.parse.return_value.output_parsed = (
        LLMPlan(
            intent="find_food",
            required_capabilities=[
                "food"
            ],
            entities=PlanEntities(
                location="Maxwell Food Centre"
            ),
        )
    )

    plan = create_llm_plan(
        "Find dinner near Maxwell Food Centre"
    )

    assert (
        plan.required_capabilities[0]
        == "food"
    )

    assert (
        plan.entities.location
        == "Maxwell Food Centre"
    )
