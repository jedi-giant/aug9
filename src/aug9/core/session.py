from aug9.core.memory import ConversationState, UserMemory
from aug9.core.database import get_memories, save_memory


# Per-user in-process session state.
# This avoids the old single global session leaking between users.
_sessions: dict[str, ConversationState] = {}


def get_memory(
    user_id: str,
) -> ConversationState:

    # Load persisted long-term memories from the database.
    memories = get_memories(
        user_id
    )

    preferences: dict[str, list[UserMemory]] = {}

    for (
        category,
        value,
        memory_type,
        confidence,
        expires,
    ) in memories:

        preferences.setdefault(
            category,
            []
        ).append(
            UserMemory(
                value=value,
                memory_type=memory_type,
                confidence=confidence,
                expires=bool(expires),
            )
        )

    # Restore this user's temporary/session state if it exists.
    existing_state = _sessions.get(
        user_id
    )

    if existing_state is None:
        existing_state = ConversationState()

    return ConversationState(
        current_place=existing_state.current_place,
        last_intent=existing_state.last_intent,
        history=existing_state.history,
        preferences=preferences,
    )


def update_memory(
    user_id: str,
    state: ConversationState,
    *,
    persist: bool = True,
) -> None:

    # Store temporary/session state separately for each user.
    _sessions[user_id] = state

    # Persist long-term preferences to the database.
    if not persist:
        return

    for category, values in state.preferences.items():

        for memory in values:

            save_memory(
                user_id,
                category,
                memory.value,
                memory.memory_type,
                memory.confidence,
                memory.expires,
            )
