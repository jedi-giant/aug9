from aug9.core.planner import Plan
from aug9.core.planner_agent import LLMPlan


def llm_plan_to_plan(
    llm_plan: LLMPlan,
) -> Plan:

    return Plan(
        intent=llm_plan.intent,
        required_capabilities=llm_plan.required_capabilities,
        entities=(
            llm_plan.entities.model_dump()
            if hasattr(llm_plan.entities, "model_dump")
            else llm_plan.entities
        ),
    )
