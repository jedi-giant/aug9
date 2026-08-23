from aug9.core.memory import ConversationState, UserMemory


def retrieve_relevant_memory(
    context: ConversationState,
    user_input: str,
) -> ConversationState:

    keywords = user_input.lower()

    filtered_preferences = {}

    for category, memories in context.preferences.items():

        relevant = []

        for memory in memories:

            if (
                category.lower() in keywords
                or memory.value.lower() in keywords
                or category in [
                    "food",
                    "preference",
                    "dislike",
                ]
                and any(
                    word in keywords
                    for word in [
                        "eat",
                        "food",
                        "dinner",
                        "lunch",
                        "meal",
                    ]
                )
            ):
                relevant.append(memory)

        if relevant:
            filtered_preferences[category] = relevant

    return ConversationState(
        current_place=context.current_place,
        last_intent=context.last_intent,
        history=context.history,
        preferences=filtered_preferences,
    )
