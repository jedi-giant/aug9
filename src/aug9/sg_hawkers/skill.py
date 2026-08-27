import math
import re
from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_hawkers.provider import HawkerProvider, distance_km


MAX_COMFORTABLE_WALK_KM = 1.2


class SgHawkersSkill(Aug9Skill):
    name = "sg_hawkers"
    description = "Discover active Singapore hawker centres from governed data"
    version = "0.1.0"

    def __init__(self, provider: HawkerProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["hawkers"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        query = entities.get("location") or self._extract_location(context.intent)
        if (
            context.current_place is not None
            and context.current_place.latitude is not None
            and context.current_place.longitude is not None
        ):
            places = self.provider.discover_near(
                context.current_place.latitude,
                context.current_place.longitude,
            )
        else:
            places = self.provider.discover(str(query) if query else None)
        if not places:
            return SkillResult(
                success=False,
                summary="No matching active hawker centres were found.",
            )

        ranked_places = []
        for place in places:
            item = place.model_dump()
            if (
                context.current_place is not None
                and context.current_place.latitude is not None
                and context.current_place.longitude is not None
            ):
                calculated_distance = distance_km(
                    context.current_place.latitude,
                    context.current_place.longitude,
                    place,
                )
                if math.isfinite(calculated_distance):
                    item["distance_km"] = round(calculated_distance, 1)
            ranked_places.append(item)

        summary_items = []
        for item in ranked_places:
            distance = item.get("distance_km")
            if distance is None:
                summary_items.append(item["name"])
                continue
            travel_guidance = (
                "walking may be practical"
                if distance <= MAX_COMFORTABLE_WALK_KM
                else "consider public transport"
            )
            summary_items.append(
                f'{item["name"]} ({distance:.1f} km away; {travel_guidance})'
            )

        return SkillResult(
            success=True,
            data={"places": ranked_places},
            summary="Nearby hawker centres: " + ", ".join(summary_items) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"Get directions to {place.name}",
                    url=(
                        "https://www.google.com/maps/dir/?api=1"
                        f"&destination={quote_plus(place.name)}"
                    ),
                    metadata={
                        "capability": "hawkers",
                        "place": place.name,
                        "distance_km": ranked_places[index].get("distance_km"),
                    },
                )
                for index, place in enumerate(places)
            ],
        )

    @staticmethod
    def _extract_location(intent: str | None) -> str | None:
        if not intent:
            return None
        match = re.search(
            r"\b(?:near|around|at)\s+(.+?)(?:[?.!]|$)",
            intent,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else None
