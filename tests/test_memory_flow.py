import pytest

from aug9.core import database
from aug9.core.session import (
    get_memory,
    update_memory,
)
from aug9.core.memory import ConversationState
from aug9.core.models import Place
from aug9.core import session


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "memory.db")
    database.initialise_database()
    session._sessions.clear()


def test_previous_location_is_remembered():

    place = Place(
        name="Maxwell Food Centre",
        place_type="hawker_centre",
        address="1 Kadayanallur Street",
        postal_code="069184",
        latitude=1.280331,
        longitude=103.844747,
    )

    update_memory(
        "test_user",
        ConversationState(
            current_place=place
        )
    )

    memory = get_memory("test_user")

    assert (
        memory.current_place.name
        == "Maxwell Food Centre"
    )


def test_conversation_location_survives_process_cache_reset():
    place = Place(name="Punggol", latitude=1.405, longitude=103.902)
    update_memory(
        "context_user",
        ConversationState(
            current_place=place,
            last_intent="Find an indoor playground near Punggol",
            history=["Find an indoor playground near Punggol"],
        ),
        session_id="conversation-a",
        persist=False,
    )

    session._sessions.clear()
    restored = get_memory("context_user", session_id="conversation-a")

    assert restored.current_place == place
    assert restored.last_intent == "Find an indoor playground near Punggol"


def test_conversation_locations_are_isolated_by_session():
    update_memory(
        "same_user",
        ConversationState(current_place=Place(name="Punggol")),
        session_id="punggol-chat",
        persist=False,
    )

    other_chat = get_memory("same_user", session_id="new-chat")

    assert other_chat.current_place is None
