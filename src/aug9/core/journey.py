from aug9.core.config import composite_journeys_enabled
from aug9.core.context import UserContext
from aug9.core.executor import ExecutionResult
from aug9.core.memory import ConversationState, JourneyState
from aug9.core.planner import Plan


JOURNEY_CAPABILITIES = {"events", "food", "weather", "transport", "lifeops"}

def is_composite_plan(plan: Plan) -> bool:
    capabilities = JOURNEY_CAPABILITIES.intersection(plan.required_capabilities)
    return "lifeops" in capabilities or len(capabilities - {"lifeops"}) >= 2


def build_journey_state(
    previous: ConversationState,
    plan: Plan,
    context: UserContext,
    execution: ExecutionResult,
) -> JourneyState | None:
    """Create the small state object needed to continue a composite journey."""
    if not composite_journeys_enabled() or not is_composite_plan(plan):
        return None

    existing = previous.journey
    original_intent = (
        existing.original_intent
        if existing is not None and existing.status in {"clarifying", "partial"}
        else plan.intent
    )
    requested_capabilities = list(
        dict.fromkeys(
            [
                *(existing.requested_capabilities if existing is not None else []),
                *plan.required_capabilities,
            ]
        )
    )
    resolved_slots = dict(existing.resolved_slots if existing is not None else {})
    if context.current_place is not None:
        resolved_slots["origin"] = context.current_place.model_dump(
            exclude_none=True
        )

    lifeops = execution.outputs.get("lifeops")
    lifeops_data = getattr(lifeops, "data", {})
    selected_stops = list(lifeops_data.get("itinerary", []))
    pending_slots = [] if context.current_place is not None else ["origin"]
    has_destination = any(
        stop.get("type") != "start" and stop.get("location")
        for stop in selected_stops
    )
    if context.current_place is not None and not has_destination:
        pending_slots.append("destination")

    if pending_slots:
        status = "clarifying" if pending_slots == ["origin"] else "partial"
    else:
        status = "ready"

    return JourneyState(
        journey_type=str(plan.entities.get("plan_type") or "day"),
        original_intent=original_intent,
        requested_capabilities=requested_capabilities,
        resolved_slots=resolved_slots,
        pending_slots=pending_slots,
        selected_stops=selected_stops,
        status=status,
    )
