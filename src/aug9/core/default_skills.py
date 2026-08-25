from aug9.core.skill_registry import SkillRegistry, skill_registry
from aug9.sg_place import OneMapProvider, SgPlaceSkill
from aug9.sg_weather import DataGovSgWeatherProvider, SgWeatherSkill


def register_default_skills(registry: SkillRegistry = skill_registry) -> SkillRegistry:
    if registry.get("sg_place") is None:
        registry.register(SgPlaceSkill(OneMapProvider.from_environment()))
    if registry.get("sg_weather") is None:
        registry.register(SgWeatherSkill(DataGovSgWeatherProvider()))
    return registry
