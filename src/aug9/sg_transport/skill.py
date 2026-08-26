import re
from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.models import SearchStatus
from aug9.sg_place.provider import PlaceProvider
from aug9.sg_transport.provider import RouteProvider


MAX_RECOMMENDED_WALK_METERS = 1500.0
LONG_TRANSIT_JOURNEY_METERS = 5000.0


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

        distance = result.route.distance_meters
        recommended_mode = "walk"
        summary = result.route.summary
        travel_mode = "walking"
        action_label = "Open walking directions"

        if distance is not None and distance > MAX_RECOMMENDED_WALK_METERS:
            recommended_mode = "public_transport"
            travel_mode = "transit"
            action_label = "Open public transport directions"
            distance_km = distance / 1000
            if distance > LONG_TRANSIT_JOURNEY_METERS:
                summary = (
                    f"{origin.name} to {destination.name} is about "
                    f"{distance_km:.1f} km. Public transport is recommended; "
                    "taxi or private hire is an alternative."
                )
            else:
                summary = (
                    f"{origin.name} to {destination.name} is about "
                    f"{distance_km:.1f} km. Public transport is recommended "
                    "instead of walking."
                )

        route_data = result.route.model_dump()
        route_data["summary"] = summary
        actions = [
            SkillAction(
                type="open_url",
                label=action_label,
                url=self._directions_url(origin.name, destination.name, travel_mode),
                metadata={
                    "capability": "transport",
                    "travel_mode": recommended_mode,
                },
            )
        ]
        if distance is not None and distance > LONG_TRANSIT_JOURNEY_METERS:
            actions.append(
                SkillAction(
                    type="open_url",
                    label="Open taxi or driving directions",
                    url=self._directions_url(origin.name, destination.name, "driving"),
                    metadata={
                        "capability": "transport",
                        "travel_mode": "taxi_or_drive",
                    },
                )
            )

        return SkillResult(
            success=True,
            data={
                "route": route_data,
                "status": result.status.value,
                "recommended_mode": recommended_mode,
            },
            summary=summary,
            actions=actions,
        )

    @staticmethod
    def _directions_url(origin: str, destination: str, travel_mode: str) -> str:
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={quote_plus(origin)}"
            f"&destination={quote_plus(destination)}"
            f"&travelmode={travel_mode}"
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
