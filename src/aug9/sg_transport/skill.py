import re
import math
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
STRAIGHT_LINE_WALK_METERS = 1200.0


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
                summary=(
                    "Where are you starting from, and where are you heading? "
                    "Share both places and I'll work out the route."
                ),
            )

        explicit_mode = self._requested_mode(entities, context.intent)
        straight_distance = self._straight_distance_meters(origin, destination)
        selected_mode = explicit_mode or (
            "walk"
            if straight_distance is not None
            and straight_distance <= STRAIGHT_LINE_WALK_METERS
            else "public_transport"
        )

        used_mode_fallback = False
        try:
            route_for_mode = getattr(self.route_provider, "route_for_mode", None)
            if route_for_mode is not None:
                result = route_for_mode(origin, destination, selected_mode)
            else:
                used_mode_fallback = selected_mode != "walk"
                result = self.route_provider.route(origin, destination)
        except ValueError as exc:
            return SkillResult(success=False, summary=str(exc))

        if (
            (result.status != SearchStatus.SUCCESS or result.route is None)
            and selected_mode != "walk"
        ):
            used_mode_fallback = True
            result = self.route_provider.route(origin, destination)

        if result.status != SearchStatus.SUCCESS or result.route is None:
            return SkillResult(success=False, summary=result.message)

        distance = result.route.distance_meters
        policy_distance = (
            straight_distance
            if selected_mode == "public_transport"
            and not used_mode_fallback
            and straight_distance is not None
            else distance
        )
        recommended_mode = selected_mode
        summary = result.route.summary
        travel_mode = {
            "walk": "walking",
            "public_transport": "transit",
            "drive": "driving",
            "cycle": "bicycling",
        }.get(recommended_mode, "transit")
        action_label = {
            "walk": "Open walking directions",
            "public_transport": "Open public transport directions",
            "drive": "Open driving directions",
            "cycle": "Open cycling directions",
        }.get(recommended_mode, "Open directions")

        if used_mode_fallback and selected_mode == "public_transport":
            distance_text = (
                f" is about {distance / 1000:.1f} km"
                if distance is not None
                else ""
            )
            summary = (
                f"{origin.name} to {destination.name}{distance_text}. "
                "Public transport makes more sense — open the directions below "
                "for the latest options."
            )

        if (
            explicit_mode is None
            and policy_distance is not None
            and policy_distance > MAX_RECOMMENDED_WALK_METERS
            and (selected_mode == "walk" or used_mode_fallback)
        ):
            recommended_mode = "public_transport"
            travel_mode = "transit"
            action_label = "Open public transport directions"
            distance_km = policy_distance / 1000
            if policy_distance > LONG_TRANSIT_JOURNEY_METERS:
                summary = (
                    f"A bit far to walk, this one — about {distance_km:.1f} km. "
                    "Public transport makes more sense; taxi or private hire "
                    "also can."
                )
            else:
                summary = (
                    f"A bit far to walk, this one — about {distance_km:.1f} km. "
                    "Public transport makes more sense."
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
        if (
            recommended_mode == "public_transport"
            and policy_distance is not None
            and policy_distance > LONG_TRANSIT_JOURNEY_METERS
        ):
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
    def _requested_mode(entities: dict[str, Any], intent: str | None) -> str | None:
        requested = str(entities.get("travel_mode") or "").casefold()
        text = (intent or "").casefold()
        if requested in {"walk", "walking"} or "walk" in text:
            return "walk"
        if requested in {"cycle", "cycling", "bike"} or any(
            word in text for word in ("cycle", "cycling", "bike")
        ):
            return "cycle"
        if requested in {"drive", "driving", "taxi"} or any(
            word in text for word in ("drive", "driving", "taxi")
        ):
            return "drive"
        if requested in {"public_transport", "transit", "mrt", "bus"} or any(
            phrase in text for phrase in ("public transport", "transit", "mrt", "bus")
        ):
            return "public_transport"
        return None

    @staticmethod
    def _straight_distance_meters(origin: Place, destination: Place) -> float | None:
        if any(
            value is None
            for value in (
                origin.latitude,
                origin.longitude,
                destination.latitude,
                destination.longitude,
            )
        ):
            return None
        radius_meters = 6_371_000.0
        phi1, phi2 = math.radians(origin.latitude), math.radians(destination.latitude)
        delta_phi = math.radians(destination.latitude - origin.latitude)
        delta_lambda = math.radians(destination.longitude - origin.longitude)
        value = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return radius_meters * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))

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
