from pydantic import BaseModel

from aug9.core.context import UserContext
from aug9.core.planner import Plan
from aug9.core.capabilities import CAPABILITIES

class ExecutionResult(BaseModel):
    plan: Plan
    outputs: dict[str, object]

def execute_plan(
    plan: Plan,
    context: UserContext,
) -> ExecutionResult:

    outputs = {}

    execution_order = [
        "place_resolution",
        "food",
        "weather",
        "transport",
    ]

    for capability in execution_order:

        if capability not in plan.required_capabilities:
            continue

        tool = CAPABILITIES.get(capability)

        if tool is None:
            outputs[capability] = "No handler available"
            continue

        handler = tool["handler"]

        outputs[capability] = handler(
            context,
            plan.entities,
        )

    return ExecutionResult(
        plan=plan,
        outputs=outputs,
    )
