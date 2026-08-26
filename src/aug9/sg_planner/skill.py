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
        return SkillResult(
            success=True,
            data={
                "plan_type": entities.get("plan_type", "day"),
                "location_available": has_location,
            },
            summary="Singapore day-plan coordination is active.",
        )
