from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_playgrounds.provider import PlaygroundProvider


class SgPlaygroundsSkill(Aug9Skill):
    name = "sg_playgrounds"
    description = "Find Singapore playgrounds from a governed local dataset"
    version = "0.1.0"

    def __init__(self, provider: PlaygroundProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["playgrounds"]

    def execute(self, context: UserContext, entities: dict[str, Any]) -> SkillResult:
        place = context.current_place
        latitude = place.latitude if place else None
        longitude = place.longitude if place else None
        playgrounds = self.provider.discover(latitude=latitude, longitude=longitude)
        if not playgrounds:
            return SkillResult(success=False, summary="I couldn't find a matching playground yet.")
        descriptions = []
        for playground in playgrounds:
            distance = (
                f"about {playground.distance_km:.1f} km away"
                if playground.distance_km is not None
                else playground.address
            )
            details = [value for value in (distance, playground.age_fit) if value]
            if playground.has_water_play:
                details.append("water play")
            elif playground.is_sheltered:
                details.append("sheltered")
            suffix = " — " + ", ".join(details) if details else ""
            descriptions.append(f"{playground.name}{suffix}")
        return SkillResult(
            success=True,
            data={"playgrounds": [playground.__dict__ for playground in playgrounds]},
            summary="Here are a few playgrounds to consider: " + "; ".join(descriptions) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"Get directions to {playground.name}",
                    url="https://www.google.com/maps/dir/?api=1&destination=" + quote_plus(playground.address or playground.name),
                    metadata={"capability": "playgrounds", "place": playground.name},
                )
                for playground in playgrounds
            ],
        )
