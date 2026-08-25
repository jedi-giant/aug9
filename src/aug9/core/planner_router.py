from aug9.core.config import PLANNER_MODE
from aug9.core.planner import create_plan
from aug9.core.planner_agent import create_llm_plan


def plan(
    user_input: str,
    memory=None,
):

    if PLANNER_MODE == "llm":
        llm_plan = create_llm_plan(
            user_input,
            memory,
        )
        rule_plan = create_plan(user_input)

        llm_plan.required_capabilities = list(
            dict.fromkeys(
                [
                    *llm_plan.required_capabilities,
                    *rule_plan.required_capabilities,
                ]
            )
        )

        for name, value in rule_plan.entities.items():
            if getattr(llm_plan.entities, name, None) is None:
                setattr(llm_plan.entities, name, value)

        return llm_plan

    return create_plan(
        user_input
    )
