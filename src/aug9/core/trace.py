from pydantic import BaseModel

from aug9.core.context import UserContext
from aug9.core.planner import Plan
from aug9.core.executor import ExecutionResult


class AgentTrace(BaseModel):
    user_input: str
    plan: Plan
    context: UserContext
    execution: ExecutionResult
    response: str
