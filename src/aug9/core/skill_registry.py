from aug9.core.skill import Aug9Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Aug9Skill] = {}

    def register(self, skill: Aug9Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        self._skills[skill.name] = skill

    def unregister(self, skill_name: str) -> None:
        self._skills.pop(skill_name, None)

    def get(self, skill_name: str) -> Aug9Skill | None:
        return self._skills.get(skill_name)

    def list_skills(self) -> list[Aug9Skill]:
        return list(self._skills.values())

    def find_by_capability(self, capability: str) -> Aug9Skill | None:
        return next(
            (skill for skill in self._skills.values() if skill.can_handle(capability)),
            None,
        )


skill_registry = SkillRegistry()
