from typing import Any

from pydantic import BaseModel, Field

from aug9.core.executor import ExecutionResult
from aug9.core.responder import compose_response
from aug9.core.skill import SkillAction, SkillResult


class AgentResponse(BaseModel):
    response: str
    actions: list[SkillAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def compose_agent_response(execution: ExecutionResult) -> AgentResponse:
    actions: list[SkillAction] = []
    skill_data: dict[str, Any] = {}

    for capability, output in execution.outputs.items():
        if not isinstance(output, SkillResult):
            continue
        actions.extend(output.actions)
        if output.data:
            skill_data[capability] = output.data

    return AgentResponse(
        response=compose_response(execution),
        actions=actions,
        metadata={"skills": skill_data} if skill_data else {},
    )
