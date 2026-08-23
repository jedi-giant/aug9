from pydantic import BaseModel

from aug9.core.context import UserContext
from aug9.core.planner import Plan
from aug9.core.executor import ExecutionResult


class AgentState(BaseModel):
    user_input: str
    context: UserContext | None = None
    plan: Plan | None = None
    execution: ExecutionResult | None = None
    response: str | None = None
