from typing import Any

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillResult
from aug9.models import SearchStatus
from aug9.sg_weather.provider import WeatherProvider


class SgWeatherSkill(Aug9Skill):
    name = "sg_weather"
    description = "Provide location-aware Singapore weather forecasts"
    version = "0.1.0"

    def __init__(self, provider: WeatherProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["weather"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        if context.current_place is None:
            return SkillResult(success=False, summary="No location available")

        result = self.provider.forecast(context.current_place)
        if result.status != SearchStatus.SUCCESS or result.weather is None:
            return SkillResult(success=False, summary=result.message)

        return SkillResult(
            success=True,
            data={
                "weather": result.weather.model_dump(),
                "status": result.status.value,
            },
            summary=f"Weather forecast: {result.weather.forecast}.",
        )
