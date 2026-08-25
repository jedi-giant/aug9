import re
from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_hawkers.provider import HawkerProvider


class SgHawkersSkill(Aug9Skill):
    name = "sg_hawkers"
    description = "Discover hawker centres in Aug9's curated Singapore catalog"
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
        places = self.provider.discover(str(query) if query else None)
        if not places:
            return SkillResult(
                success=False,
                summary="No hawker centres are available in the current catalog.",
            )

        return SkillResult(
            success=True,
            data={"places": [place.model_dump() for place in places]},
            summary="Hawker centres: " + ", ".join(place.name for place in places) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"Open {place.name}",
                    url=(
                        "https://www.google.com/maps/search/?api=1"
                        f"&query={quote_plus(place.name)}"
                    ),
                    metadata={"capability": "hawkers", "place": place.name},
                )
                for place in places
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
