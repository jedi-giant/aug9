from aug9.core.context_builder import build_context
from aug9.core.executor import execute_plan
from aug9.core.planner_router import plan as create_plan
from aug9.core.responder import compose_response
from aug9.core.planner_adapter import llm_plan_to_plan
from aug9.core.trace import AgentTrace
from aug9.core.session import get_memory
from aug9.core.memory_agent import extract_memories
from aug9.core.database import save_memory
from aug9.core.memory_retriever import retrieve_relevant_memory
from aug9.core.memory_ranker import rank_memories
from aug9.core.semantic_memory import retrieve_semantic_memories

def run_aug9(
    user_input: str,
) -> str:

    extracted = extract_memories(
        user_input
    )

    for memory in extracted.memories:
        save_memory(
            "default_user",
            memory.category,
            memory.value,
            memory.memory_type,
            memory.confidence,
            memory.expires,
        )

    memory = get_memory()
    
    relevant_memory = retrieve_relevant_memory(
        memory,
        user_input,
    )
    semantic_memories = retrieve_semantic_memories(
        user_input
    )

    candidate_memories = []

    for category, memories in relevant_memory.preferences.items():
        for memory_item in memories:
            candidate_memories.append(
                {
                    "category": category,
                    "value": memory_item.value,
                    "type": memory_item.memory_type,
                }
            )


    ranked_memory = rank_memories(
        user_input,
        candidate_memories,
    )


    ranked_preferences = {}

    for memory_item in ranked_memory.memories:
        ranked_preferences.setdefault(
            "memory",
            []
        ).append(
            memory_item.value
        )

    raw_plan = create_plan(
        user_input,
        memory,
    )

    memory = get_memory()

    raw_plan = create_plan(
        user_input,
        memory,
    )
    plan = llm_plan_to_plan(
        raw_plan
    )
    context = build_context(
        user_input,
        plan.entities,
    )

    execution = execute_plan(
        plan,
        context,
    )

    response = compose_response(
        execution
    )
    trace = AgentTrace(
        user_input=user_input,
        plan=plan,
        context=context,
        execution=execution,
        response=response,
    )

    print("=== Aug9 Trace ===")
    print(
        trace.model_dump_json(
            indent=2
        )
    )
    return response
