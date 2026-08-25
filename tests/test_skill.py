from aug9.core.context import UserContext
from aug9.core.skill import SkillAction, SkillResult


def test_skill_models_use_independent_mutable_defaults():
    first = SkillResult(success=True)
    second = SkillResult(success=True)

    first.data["value"] = "hello"

    assert second.data == {}
    assert SkillAction(type="open_url", label="Open").metadata == {}
