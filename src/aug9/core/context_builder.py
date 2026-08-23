import os

from dotenv import load_dotenv

from aug9.core.context import UserContext
from aug9.core.memory import ConversationState
from aug9.core.session import get_memory, update_memory
from aug9.core.converters.location import location_to_place
from aug9.onemap import get_token, search_location

def build_context(
    user_input: str,
    entities: dict[str, str] | None = None,
) -> UserContext:

    load_dotenv()

    base_url = os.getenv(
        "ONEMAP_BASE_URL"
    )

    email = os.getenv(
        "ONEMAP_EMAIL"
    )

    password = os.getenv(
        "ONEMAP_PASSWORD"
    )

    token = get_token(
        base_url,
        email,
        password,
    )

    if token is None:
        return UserContext(
            intent=user_input
        )

    query = user_input

    if entities and entities.get("location"):
        query = entities["location"]

    result = search_location(
        base_url,
        token,
        query,
    )

    if result.location is not None:
    
        place = location_to_place(
            result.location
        )

        update_memory(
            ConversationState(
                current_place=place,
                last_intent=user_input,
                history=[
                    user_input
                ],
            )
        )

        return UserContext(
            current_place=place,
            intent=user_input,
            memory=get_memory(),
        )


    memory = get_memory()

    return UserContext(
        current_place=memory.current_place,
        intent=user_input,
        memory=memory,
    )
