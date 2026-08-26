import json
import os
import time

from aug9.core.context_builder import build_context
from aug9.core.executor import execute_plan
from aug9.core.planner_router import plan as create_plan
from aug9.core.responder import compose_response
from aug9.core.planner_adapter import llm_plan_to_plan
from aug9.core.trace import AgentTrace
from aug9.core.session import get_memory
from aug9.core.memory_agent import extract_memories, should_extract_memories
from aug9.core.database import save_memory
from aug9.core.agent_response import AgentResponse, compose_agent_response


def run_aug9(
    user_input: str,
    user_id: str,
    session_id: str | None = None,
    structured: bool = False,
) -> str | AgentResponse:
    request_started = time.perf_counter()
    stage_started = request_started
    extracted_memories = []
    if should_extract_memories(user_input):
        extracted_memories = extract_memories(user_input).memories

    for memory in extracted_memories:
        save_memory(
            user_id,
            memory.category,
            memory.value,
            memory.memory_type,
            memory.confidence,
            memory.expires,
        )
    timings_ms = {
        "memory": int((time.perf_counter() - stage_started) * 1000),
    }

    stage_started = time.perf_counter()
    memory = get_memory(user_id)
    timings_ms["memory_load"] = int(
        (time.perf_counter() - stage_started) * 1000
    )

    stage_started = time.perf_counter()
    raw_plan = create_plan(
        user_input,
        memory,
    )
    timings_ms["planning"] = int(
        (time.perf_counter() - stage_started) * 1000
    )

    plan = llm_plan_to_plan(
        raw_plan
    )

    stage_started = time.perf_counter()
    context = build_context(
        user_input,
        plan.entities,
        user_id=user_id,
        memory=memory,
    )
    timings_ms["context"] = int(
        (time.perf_counter() - stage_started) * 1000
    )

    stage_started = time.perf_counter()
    execution = execute_plan(
        plan,
        context,
    )
    timings_ms["execution"] = int(
        (time.perf_counter() - stage_started) * 1000
    )

    stage_started = time.perf_counter()
    response = compose_response(
        execution
    )
    timings_ms["response"] = int(
        (time.perf_counter() - stage_started) * 1000
    )
    timings_ms["total"] = int(
        (time.perf_counter() - request_started) * 1000
    )

    trace = AgentTrace(
        user_input=user_input,
        plan=plan,
        context=context,
        execution=execution,
        response=response,
        timings_ms=timings_ms,
    )

    print(json.dumps({"event": "aug9_request_timing", **timings_ms}))
    if os.getenv("AUG9_TRACE_ENABLED", "").casefold() in {"1", "true", "yes"}:
        print("=== Aug9 Trace ===")
        print(trace.model_dump_json(indent=2))

    if structured:
        agent_response = compose_agent_response(execution)
        agent_response.metadata["timings_ms"] = timings_ms
        return agent_response
    return response
