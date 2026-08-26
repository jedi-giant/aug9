from typing import Any

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillResult


class SgPlannerSkill(Aug9Skill):
    """Marks a request for orchestration across existing Singapore skills."""

    name = "sg_planner"
    description = "Coordinate Singapore weather, food, and activity planning"
    version = "0.1.0"

    @property
    def capabilities(self) -> list[str]:
        return ["lifeops"]

    def execute(self, context: UserContext, entities: dict[str, Any]) -> SkillResult:
        has_location = bool(context.current_place or entities.get("location"))
        outputs = entities.get("_lifeops_outputs", {})
        itinerary = self._build_itinerary(context, outputs)
        return SkillResult(
            success=True,
            data={
                "plan_type": entities.get("plan_type", "day"),
                "location_available": has_location,
                "itinerary": itinerary,
                "weather": self._skill_data(outputs, "weather").get("weather"),
                "transport": self._skill_data(outputs, "transport").get("route"),
            },
            summary=(
                f"Your Singapore day plan has {len(itinerary)} planned stops."
                if itinerary
                else "Singapore day-plan coordination is active."
            ),
        )

    @classmethod
    def _build_itinerary(
        cls,
        context: UserContext,
        outputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        itinerary: list[dict[str, Any]] = []
        if context.current_place is not None:
            itinerary.append(
                {
                    "order": 1,
                    "type": "start",
                    "title": f"Start at {context.current_place.name}",
                    "location": context.current_place.name,
                }
            )

        food = outputs.get("food")
        recommendations = getattr(food, "recommendations", [])
        if recommendations:
            recommendation = recommendations[0]
            itinerary.append(
                {
                    "order": len(itinerary) + 1,
                    "type": "food",
                    "title": recommendation.name,
                    "description": recommendation.description,
                    "location": recommendation.place.name,
                }
            )

        for event in cls._skill_data(outputs, "events").get("events", []):
            itinerary.append(
                {
                    "order": len(itinerary) + 1,
                    "type": "event",
                    "title": event.get("name"),
                    "starts_at": event.get("starts_at"),
                    "ends_at": event.get("ends_at"),
                    "location": event.get("address"),
                    "booking_url": event.get("booking_url") or event.get("source_url"),
                }
            )
        return itinerary

    @staticmethod
    def _skill_data(outputs: dict[str, Any], capability: str) -> dict[str, Any]:
        output = outputs.get(capability)
        data = getattr(output, "data", {})
        return data if isinstance(data, dict) else {}
