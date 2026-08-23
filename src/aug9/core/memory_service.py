from aug9.core.context import ConversationState


class MemoryService:

    def __init__(self):
        self.state = ConversationState()

    def get_memory(self):
        return self.state

    def update(
        self,
        intent: str,
    ):
        self.state.last_intent = intent
        self.state.history.append(intent)
