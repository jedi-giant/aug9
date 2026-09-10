from pydantic import BaseModel

from aug9.core.context import UserContext
from aug9.core.planner import Plan
from aug9.core.capabilities import CAPABILITIES
from aug9.core.default_skills import register_default_skills
from aug9.core.skill import SkillResult
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
    execution_entities["_is_lifeops"] = is_lifeops

    execution_order = [
        "place_resolution",
        "playgrounds",
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

        if capability == "lifeops":
            execution_entities["_lifeops_outputs"] = dict(outputs)

        if capability == "transport" and is_lifeops:
            if context.current_place is None:
                continue
            food_output = outputs.get("food")
            food_items = getattr(food_output, "data", {}).get("places", [])
            event_output = outputs.get("events")
            event_items = getattr(event_output, "data", {}).get("events", [])
            next_stop = food_items[0] if food_items else (
                event_items[0] if event_items else None
            )
            if next_stop is None:
                continue
            destination = next_stop.get("address") or next_stop.get("name")
            if not destination:
                continue
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
            elif capability == "playgrounds" and execution_entities.get(
                "requested_entity_name"
            ):
                playgrounds = getattr(outputs[capability], "data", {}).get(
                    "playgrounds", []
                )
                if getattr(outputs[capability], "success", False) and len(playgrounds) == 1:
                    item = playgrounds[0]
                    anchor = Place(
                        name=item["name"],
                        place_type="playground",
                        address=item.get("address"),
                        latitude=item.get("latitude"),
                        longitude=item.get("longitude"),
                    )
                    memory = (
                        context.memory.model_copy(update={"current_place": anchor})
                        if context.memory is not None
                        else None
                    )
                    context = context.model_copy(
                        update={"current_place": anchor, "memory": memory}
                    )
                    outputs["place_resolution"] = SkillResult(
                        success=True,
                        data={"place": anchor.model_dump(exclude_none=True)},
                        summary=f"Resolved {anchor.name} from Aug9's catalogue.",
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
