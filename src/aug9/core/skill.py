from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from aug9.core.context import UserContext


class SkillAction(BaseModel):
    type: str
    label: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillOutcome(StrEnum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    DEFERRED = "deferred"


class SkillResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    actions: list[SkillAction] = Field(default_factory=list)
    outcome: SkillOutcome | None = None

    @property
    def resolved_outcome(self) -> SkillOutcome:
        if self.outcome is not None:
            return self.outcome
        return SkillOutcome.MATCHED if self.success else SkillOutcome.UNMATCHED


class Aug9Skill(ABC):
    """Contract implemented by runtime-discoverable Aug9 skills."""

    name: str
    description: str
    version: str = "0.1.0"

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        raise NotImplementedError

    def can_handle(self, capability: str) -> bool:
        return capability in self.capabilities

    @abstractmethod
    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        raise NotImplementedError
