import re
from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_hotels.provider import HotelProvider


class SgHotelsSkill(Aug9Skill):
    name = "sg_hotels"
    description = "Discover licensed Singapore hotels from governed data"
    version = "0.1.0"

    def __init__(self, provider: HotelProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["hotels"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        query = entities.get("location") or self._extract_query(context.intent)
        places = self.provider.discover(str(query) if query else None)
        if not places:
            return SkillResult(
                success=False,
                summary="No matching licensed hotels were found.",
            )
        return SkillResult(
            success=True,
            data={"places": [place.model_dump() for place in places]},
            summary="Licensed hotels: " + ", ".join(p.name for p in places) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"Open {place.name}",
                    url=(
                        "https://www.google.com/maps/search/?api=1"
                        f"&query={quote_plus(place.name)}"
                    ),
                    metadata={"capability": "hotels", "place": place.name},
                )
                for place in places
            ],
        )

    @staticmethod
    def _extract_query(intent: str | None) -> str | None:
        if not intent:
            return None
        match = re.search(
            r"\b(?:hotel|hotels)\s+(?:named|called|near|around|at)\s+(.+?)"
            r"(?:[?.!]|$)",
            intent,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match and match.group(1).strip() else None
