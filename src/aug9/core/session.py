import json

from aug9.core import database
from aug9.core.memory import ConversationState, UserMemory
from aug9.core.models import Place
from aug9.core.database import get_memories, save_memory


# Per-user in-process session state.
# This avoids the old single global session leaking between users.
_sessions: dict[str, ConversationState] = {}


def get_memory(
    user_id: str,
    session_id: str | None = None,
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
    session_key = _session_key(user_id, session_id)
    existing_state = _sessions.get(session_key)

    if existing_state is None and session_id:
        existing_state = _load_session_state(user_id, session_id)

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
    session_id: str | None = None,
    persist: bool = True,
) -> None:

    # Store temporary/session state separately for each user.
    _sessions[_session_key(user_id, session_id)] = state

    if session_id:
        _save_session_state(user_id, session_id, state)

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


def _session_key(user_id: str, session_id: str | None) -> str:
    return f"{user_id}:{session_id}" if session_id else user_id


def _load_session_state(
    user_id: str, session_id: str
) -> ConversationState | None:
    conn = None
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT current_place, last_intent, history
            FROM conversation_contexts
            WHERE user_id = {p} AND session_id = {p}
            """,
            (user_id, session_id),
        )
        row = cursor.fetchone()
    except Exception:
        # Session context is an enhancement; a missing/unavailable table must
        # not prevent the primary chat journey from working.
        return None
    finally:
        if conn is not None:
            conn.close()
    if row is None:
        return None
    return ConversationState(
        current_place=(
            Place.model_validate(json.loads(row[0])) if row[0] else None
        ),
        last_intent=row[1],
        history=json.loads(row[2] or "[]"),
    )


def _save_session_state(
    user_id: str,
    session_id: str,
    state: ConversationState,
) -> None:
    conn = None
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            INSERT INTO conversation_contexts (
                user_id, session_id, current_place, last_intent, history
            ) VALUES ({p}, {p}, {p}, {p}, {p})
            ON CONFLICT(user_id, session_id) DO UPDATE SET
                current_place = excluded.current_place,
                last_intent = excluded.last_intent,
                history = excluded.history,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                session_id,
                (
                    state.current_place.model_dump_json()
                    if state.current_place is not None
                    else None
                ),
                state.last_intent,
                json.dumps(state.history[-20:]),
            ),
        )
        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()
