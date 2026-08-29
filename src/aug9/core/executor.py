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
    execution_entities = dict(plan.entities)
    is_lifeops = "lifeops" in plan.required_capabilities

    execution_order = [
        "place_resolution",
        "hawkers",
        "hotels",
        "events",
        "playgrounds",
        "services",
        "food",
        "weather",
        "transport",
        "lifeops",
    ]

    for capability in execution_order:

        if capability not in plan.required_capabilities:
            continue

        if capability == "lifeops":
            execution_entities["_lifeops_outputs"] = dict(outputs)

        if capability == "transport" and is_lifeops:
            if context.current_place is None:
                continue
            event_output = outputs.get("events")
            event_items = getattr(event_output, "data", {}).get("events", [])
            if not event_items:
                continue
            first_event = event_items[0]
            destination = first_event.get("address") or first_event.get("name")
            if not destination:
                continue
            execution_entities["destination"] = destination

        skill = registry.find_by_capability(capability)

        if skill is not None:
            outputs[capability] = skill.execute(context, execution_entities)
            continue

        tool = CAPABILITIES.get(capability)

        if tool is None:
            outputs[capability] = "No handler available"
            continue

        handler = tool["handler"]

        outputs[capability] = handler(
            context,
            execution_entities,
        )

    return ExecutionResult(
        plan=plan,
        outputs=outputs,
    )
