from aug9.core.config import PLANNER_MODE
from aug9.core.planner import create_plan
from aug9.core.planner_agent import create_llm_plan


def plan(
    user_input: str,
    memory=None,
):

    if PLANNER_MODE == "llm":
        rule_plan = create_plan(user_input)
        if can_use_rule_plan(rule_plan, memory):
            return rule_plan

        llm_plan = create_llm_plan(
            user_input,
            memory,
        )

        llm_plan.required_capabilities = list(
            dict.fromkeys(
                [
                    *llm_plan.required_capabilities,
                    *rule_plan.required_capabilities,
                ]
            )
        )

        if (
            any(
                capability != "place_resolution"
                for capability in rule_plan.required_capabilities
            )
            and "food" not in rule_plan.required_capabilities
        ):
            llm_plan.required_capabilities = [
                capability
                for capability in llm_plan.required_capabilities
                if capability != "food"
            ]

        for name, value in rule_plan.entities.items():
            if getattr(llm_plan.entities, name, None) is None:
                setattr(llm_plan.entities, name, value)

        return llm_plan

    return create_plan(
        user_input
    )


def can_use_rule_plan(rule_plan, memory=None) -> bool:
    capabilities = set(rule_plan.required_capabilities)
    if not capabilities or "lifeops" in capabilities:
        return False

    entities = rule_plan.entities
    remembered_place = getattr(memory, "current_place", None) is not None
    has_location = bool(entities.get("location") or remembered_place)

    if "transport" in capabilities:
        has_origin = bool(entities.get("origin") or remembered_place)
        if not (has_origin and entities.get("destination")):
            return False

    if capabilities.intersection({"weather", "food", "playgrounds"}) and not has_location:
        return False

    if "place_resolution" in capabilities and not (
        has_location
        or (entities.get("origin") and entities.get("destination"))
    ):
        return False

    if "services" in capabilities and not entities.get("service_query"):
        return False

    return True
