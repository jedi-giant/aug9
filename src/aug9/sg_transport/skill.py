import re
from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
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
        intent_origin, intent_destination = self._extract_endpoints(context.intent)
        origin_query = entities.get("origin") or intent_origin
        destination_query = entities.get("destination") or intent_destination

        origin = self._resolve(origin_query) or context.current_place
        destination = self._resolve(destination_query)
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
            actions=[
                SkillAction(
                    type="open_url",
                    label="Open directions",
                    url=(
                        "https://www.google.com/maps/dir/?api=1"
                        f"&origin={quote_plus(origin.name)}"
                        f"&destination={quote_plus(destination.name)}"
                        "&travelmode=walking"
                    ),
                    metadata={"capability": "transport"},
                )
            ],
        )

    def _resolve(self, query: Any) -> Place | None:
        if not query:
            return None
        result = self.place_provider.search(str(query))
        if result.status != SearchStatus.SUCCESS:
            return None
        return result.location

    @staticmethod
    def _extract_endpoints(intent: str | None) -> tuple[str | None, str | None]:
        if not intent:
            return None, None
        match = re.search(
            r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:[?.!]|$)",
            intent,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None, None
        return match.group(1).strip(), match.group(2).strip()
