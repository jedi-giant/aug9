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
    capability_outcomes: dict[str, str] = {}

    for capability, output in execution.outputs.items():
        if not isinstance(output, SkillResult):
            continue
        capability_outcomes[capability] = "matched" if output.success else "unmatched"
        actions.extend(output.actions)
        if output.data:
            skill_data[capability] = output.data

    metadata: dict[str, Any] = {
        "requested_capabilities": execution.plan.required_capabilities,
    }
    if skill_data:
        metadata["skills"] = skill_data
    if capability_outcomes:
        metadata["capability_outcomes"] = capability_outcomes

    return AgentResponse(
        response=compose_response(execution),
        actions=actions,
        metadata=metadata,
    )
