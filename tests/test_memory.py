from aug9.core.session import (
    get_memory,
    update_memory,
)
from aug9.core.memory import ConversationState


def test_memory_updates():

    state = ConversationState(
        last_intent="food"
    )

    update_memory(state)

    memory = get_memory()

    assert memory.last_intent == "food"
