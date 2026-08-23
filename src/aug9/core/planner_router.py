from aug9.core.config import PLANNER_MODE
from aug9.core.planner import create_plan
from aug9.core.planner_agent import create_llm_plan


def plan(
    user_input: str,
    memory=None,
):

    if PLANNER_MODE == "llm":
        return create_llm_plan(
            user_input,
            memory,
        )

    return create_plan(
        user_input
    )
