from typing import Any

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillResult
from aug9.models import SearchStatus
from aug9.sg_place.provider import PlaceProvider


class SgPlaceSkill(Aug9Skill):
    name = "sg_place"
    description = "Resolve Singapore places through a configurable place provider"
    version = "0.1.0"

    def __init__(self, provider: PlaceProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["place_resolution"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        query = entities.get("location")
        if context.current_place is not None and (
            not query
            or str(query).casefold() == context.current_place.name.casefold()
        ):
            return SkillResult(
                success=True,
                data={"place": context.current_place.model_dump()},
                summary=f"Resolved {context.current_place.name}.",
            )
        if not query:
            return SkillResult(success=False, summary="No location available")

        result = self.provider.search(str(query))
        if result.status != SearchStatus.SUCCESS or result.location is None:
            return SkillResult(success=False, summary=result.message)

        return SkillResult(
            success=True,
            data={"place": result.location.model_dump()},
            summary=f"Resolved {result.location.name}.",
        )
