from pydantic import BaseModel

from aug9.core.context import UserContext
from aug9.core.planner import Plan
from aug9.core.capabilities import CAPABILITIES
from aug9.core.default_skills import register_default_skills
from aug9.core.config import composite_journeys_enabled
from aug9.core.skill_registry import SkillRegistry, skill_registry
from aug9.core.models import Place

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
            destination = _first_journey_destination(outputs)
            if not destination:
                continue
            origin = context.current_place.name
            if origin.strip().casefold() == destination.strip().casefold():
                continue
            execution_entities["origin"] = origin
            execution_entities["destination"] = destination

        skill = registry.find_by_capability(capability)

        if skill is not None:
            outputs[capability] = skill.execute(context, execution_entities)
            if capability == "place_resolution":
                place_data = getattr(outputs[capability], "data", {}).get("place")
                if getattr(outputs[capability], "success", False) and place_data:
                    context = context.model_copy(
                        update={"current_place": Place.model_validate(place_data)}
                    )
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


def _first_journey_destination(outputs: dict[str, object]) -> str | None:
    """Select the first real stop before executing the dependent route."""
    if composite_journeys_enabled():
        food_output = outputs.get("food")
        food_places = getattr(food_output, "data", {}).get("places", [])
        if food_places:
            first_food = food_places[0]
            destination = first_food.get("address") or first_food.get("name")
            if destination:
                return str(destination)

    event_output = outputs.get("events")
    event_items = getattr(event_output, "data", {}).get("events", [])
    if event_items:
        first_event = event_items[0]
        destination = first_event.get("address") or first_event.get("name")
        if destination:
            return str(destination)
    return None
