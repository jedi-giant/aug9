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
        child_ages = tuple(
            age for age in entities.get("child_ages", []) if isinstance(age, int)
        )
        water_play = entities.get("water_play") is True
        sheltered = entities.get("sheltered") is True
        intent = (context.intent or "").casefold()
        wet_weather = any(word in intent for word in ("rain", "rainy", "wet weather"))
        playgrounds = self.provider.discover(
            latitude=latitude,
            longitude=longitude,
            child_ages=child_ages,
            water_play=water_play,
            sheltered=sheltered,
            prefer_sheltered=wet_weather and not sheltered,
        )
        if not playgrounds:
            criteria = []
            if child_ages:
                criteria.append("the requested ages")
            if water_play:
                criteria.append("water play")
            if sheltered:
                criteria.append("shelter")
            suffix = " for " + ", ".join(criteria) if criteria else " nearby"
            return SkillResult(
                success=False,
                summary=f"I couldn't find a playground matching your preferences{suffix}.",
            )
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
        preference_summary = []
        if child_ages:
            preference_summary.append(
                "ages " + ", ".join(str(age) for age in child_ages)
            )
        if water_play:
            preference_summary.append("water play")
        if sheltered or wet_weather:
            preference_summary.append("shelter")
        opening = (
            "These are the strongest nearby matches for "
            + ", ".join(preference_summary)
            + ": "
            if preference_summary
            else "Here are three nearby playgrounds to consider: "
        )
        return SkillResult(
            success=True,
            data={
                "playgrounds": [playground.__dict__ for playground in playgrounds],
                "filters": {
                    "child_ages": list(child_ages),
                    "water_play": water_play,
                    "sheltered": sheltered,
                    "weather_aware_shelter_preference": wet_weather and not sheltered,
                },
            },
            summary=opening + "; ".join(descriptions) + ".",
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
