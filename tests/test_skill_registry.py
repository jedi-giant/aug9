import pytest

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillResult
from aug9.core.skill_registry import SkillRegistry


class TestSkill(Aug9Skill):
    name = "test"
    description = "Test skill"

    @property
    def capabilities(self) -> list[str]:
        return ["testing"]

    def execute(self, context: UserContext, entities: dict) -> SkillResult:
        return SkillResult(success=True)


def test_registry_finds_skill_by_capability():
    registry = SkillRegistry()
    skill = TestSkill()
    registry.register(skill)

    assert registry.get("test") is skill
    assert registry.find_by_capability("testing") is skill
    assert registry.find_by_capability("unknown") is None


def test_registry_rejects_duplicate_names_and_can_unregister():
    registry = SkillRegistry()
    registry.register(TestSkill())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(TestSkill())

    registry.unregister("test")
    assert registry.get("test") is None
