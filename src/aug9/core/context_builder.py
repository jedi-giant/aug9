import os

from dotenv import load_dotenv

from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.core.memory import ConversationState
from aug9.core.session import get_memory, update_memory
from aug9.core.converters.location import location_to_place
from aug9.onemap import get_token, search_location
from aug9.models import SearchStatus
from aug9.sg_place.provider import OneMapProvider


def build_context(
    user_input: str,
    entities: dict[str, str] | None = None,
    user_id: str = "",
    memory: ConversationState | None = None,
    supplied_place: Place | None = None,
    session_id: str | None = None,
) -> UserContext:

    load_dotenv()

    if supplied_place is not None:
        if supplied_place.latitude is not None and supplied_place.longitude is not None:
            resolved = OneMapProvider.from_environment().reverse_geocode(
                supplied_place.latitude,
                supplied_place.longitude,
            )
            if resolved.status is SearchStatus.SUCCESS and resolved.location is not None:
                supplied_place = resolved.location
        resolved_memory = memory or get_memory(user_id, session_id=session_id)
        state = ConversationState(
            current_place=supplied_place,
            last_intent=user_input,
            history=[*resolved_memory.history, user_input][-20:],
            preferences=resolved_memory.preferences,
            journey=resolved_memory.journey,
        )
        update_memory(
            user_id, state, session_id=session_id, persist=False
        )
        return UserContext(
            current_place=supplied_place,
            intent=user_input,
            memory=state,
        )

    if memory is not None and memory.current_place is not None and not (
        entities and entities.get("location")
    ):
        memory = _remember_turn(
            user_id, session_id, memory, user_input
        )
        return UserContext(
            current_place=memory.current_place,
            intent=user_input,
            memory=memory,
        )

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
        memory = memory or get_memory(user_id, session_id=session_id)

        memory = _remember_turn(
            user_id, session_id, memory, user_input
        )

        return UserContext(
            current_place=memory.current_place,
            intent=user_input,
            memory=memory,
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

        existing_memory = memory or get_memory(user_id, session_id=session_id)

        state = ConversationState(
            current_place=place,
            last_intent=user_input,
            history=[
                *existing_memory.history,
                user_input,
            ],
            preferences=existing_memory.preferences,
            journey=existing_memory.journey,
        )

        update_memory(
            user_id,
            state,
            session_id=session_id,
            persist=False,
        )

        return UserContext(
            current_place=place,
            intent=user_input,
            memory=state,
        )

    memory = memory or get_memory(user_id, session_id=session_id)
    memory = _remember_turn(
        user_id, session_id, memory, user_input
    )

    return UserContext(
        current_place=memory.current_place,
        intent=user_input,
        memory=memory,
    )


def _remember_turn(
    user_id: str,
    session_id: str | None,
    memory: ConversationState,
    user_input: str,
) -> ConversationState:
    state = ConversationState(
        current_place=memory.current_place,
        last_intent=user_input,
        history=[*memory.history, user_input][-20:],
        preferences=memory.preferences,
        journey=memory.journey,
    )
    update_memory(user_id, state, session_id=session_id, persist=False)
    return state
