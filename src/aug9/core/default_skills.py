from aug9.core.skill_registry import SkillRegistry, skill_registry
from aug9.sg_place import OneMapProvider, SgPlaceSkill
from aug9.sg_weather import DataGovSgWeatherProvider, SgWeatherSkill
from aug9.sg_transport import OsrmRouteProvider, SgTransportSkill
from aug9.sg_hawkers import DatabaseHawkerProvider, SgHawkersSkill


def register_default_skills(registry: SkillRegistry = skill_registry) -> SkillRegistry:
    if registry.get("sg_place") is None:
        registry.register(SgPlaceSkill(OneMapProvider.from_environment()))
    if registry.get("sg_weather") is None:
        registry.register(SgWeatherSkill(DataGovSgWeatherProvider()))
    if registry.get("sg_transport") is None:
        registry.register(
            SgTransportSkill(
                OneMapProvider.from_environment(),
                OsrmRouteProvider(),
            )
        )
    if registry.get("sg_hawkers") is None:
        registry.register(SgHawkersSkill(DatabaseHawkerProvider()))
    return registry
