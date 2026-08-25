from typing import Any

from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.core.skill import Aug9Skill, SkillResult
from aug9.models import SearchStatus
from aug9.sg_place.provider import PlaceProvider
from aug9.sg_transport.provider import RouteProvider


class SgTransportSkill(Aug9Skill):
    name = "sg_transport"
    description = "Provide walking routes between Singapore places"
    version = "0.1.0"

    def __init__(
        self,
        place_provider: PlaceProvider,
        route_provider: RouteProvider,
    ) -> None:
        self.place_provider = place_provider
        self.route_provider = route_provider

    @property
    def capabilities(self) -> list[str]:
        return ["transport"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        origin = self._resolve(entities.get("origin")) or context.current_place
        destination = self._resolve(entities.get("destination"))
        if destination is None and entities.get("location"):
            destination = self._resolve(entities.get("location"))

        if origin is None or destination is None:
            return SkillResult(
                success=False,
                summary="Both origin and destination are required.",
            )

        try:
            result = self.route_provider.route(origin, destination)
        except ValueError as exc:
            return SkillResult(success=False, summary=str(exc))

        if result.status != SearchStatus.SUCCESS or result.route is None:
            return SkillResult(success=False, summary=result.message)

        return SkillResult(
            success=True,
            data={
                "route": result.route.model_dump(),
                "status": result.status.value,
            },
            summary=result.route.summary,
        )

    def _resolve(self, query: Any) -> Place | None:
        if not query:
            return None
        result = self.place_provider.search(str(query))
        if result.status != SearchStatus.SUCCESS:
            return None
        return result.location
