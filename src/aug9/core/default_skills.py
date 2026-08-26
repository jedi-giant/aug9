from aug9.core.skill_registry import SkillRegistry, skill_registry
from aug9.sg_place import OneMapProvider, SgPlaceSkill
from aug9.sg_weather import DataGovSgWeatherProvider, SgWeatherSkill
from aug9.sg_transport import OsrmRouteProvider, SgTransportSkill
from aug9.sg_hawkers import DatabaseHawkerProvider, SgHawkersSkill
from aug9.sg_hotels import DatabaseHotelProvider, SgHotelsSkill
from aug9.sg_events import DatabaseEventProvider, SgEventsSkill
from aug9.sg_services import OfficialGovernmentServiceProvider, SgServicesSkill
from aug9.sg_planner import SgPlannerSkill


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
    if registry.get("sg_hotels") is None:
        registry.register(SgHotelsSkill(DatabaseHotelProvider()))
    if registry.get("sg_events") is None:
        registry.register(SgEventsSkill(DatabaseEventProvider()))
    if registry.get("sg_services") is None:
        registry.register(SgServicesSkill(OfficialGovernmentServiceProvider()))
    if registry.get("sg_planner") is None:
        registry.register(SgPlannerSkill())
    return registry
