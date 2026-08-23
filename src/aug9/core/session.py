from aug9.core.memory import (
    ConversationState,
    UserMemory,
)

from aug9.core.database import (
    get_memories,
    save_memory,
)


USER_ID = "default_user"


_session = ConversationState()


def get_memory() -> ConversationState:
    global _session

    memories = get_memories(
        USER_ID
    )

    preferences = {}

    for (
        category,
        value,
        memory_type,
        confidence,
        expires,
    ) in memories:

        if category not in preferences:
            preferences[category] = []

        preferences[category].append(
            UserMemory(
                value=value,
                memory_type=memory_type,
                confidence=confidence,
                expires=bool(expires),
            )
        )

    _session.preferences = preferences

    return _session


def update_memory(
    state: ConversationState,
):
    global _session

    _session = state

    for category, values in state.preferences.items():

        for memory in values:

            save_memory(
                USER_ID,
                category,
                memory.value,
                memory.memory_type,
                memory.confidence,
                memory.expires,
            )
