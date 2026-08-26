from pydantic import BaseModel

from aug9.core.context import UserContext
from aug9.core.planner import Plan
from aug9.core.capabilities import CAPABILITIES
from aug9.core.default_skills import register_default_skills
from aug9.core.skill_registry import SkillRegistry, skill_registry

class ExecutionResult(BaseModel):
    plan: Plan
    outputs: dict[str, object]

def execute_plan(
    plan: Plan,
    context: UserContext,
    registry: SkillRegistry | None = None,
) -> ExecutionResult:
    registry = registry or register_default_skills(skill_registry)
    outputs = {}

    execution_order = [
        "place_resolution",
        "hawkers",
        "hotels",
        "events",
        "services",
        "food",
        "weather",
        "transport",
        "lifeops",
    ]

    for capability in execution_order:

        if capability not in plan.required_capabilities:
            continue

        skill = registry.find_by_capability(capability)

        if skill is not None:
            outputs[capability] = skill.execute(context, plan.entities)
            continue

        tool = CAPABILITIES.get(capability)

        if tool is None:
            outputs[capability] = "No handler available"
            continue

        handler = tool["handler"]

        outputs[capability] = handler(
            context,
            plan.entities,
        )

    return ExecutionResult(
        plan=plan,
        outputs=outputs,
    )
