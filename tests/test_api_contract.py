import pytest
from pydantic import ValidationError

from aug9.api.main import (
    ChatRequest,
    ChatResponse,
    configured_allowed_origins,
    require_admin,
    list_hawker_centres,
)


def test_chat_response_preserves_legacy_response_only_construction():
    result = ChatResponse(response="Hello")

    assert result.response == "Hello"
    assert result.actions == []
    assert result.metadata == {}


def test_chat_request_has_public_beta_input_bounds():
    with pytest.raises(ValidationError):
        ChatRequest(user_id="user", session_id="session", message="")
    with pytest.raises(ValidationError):
        ChatRequest(user_id="user", session_id="session", message="   ")
    with pytest.raises(ValidationError):
        ChatRequest(user_id="u" * 129, session_id="session", message="hello")
    with pytest.raises(ValidationError):
        ChatRequest(user_id="user", session_id="s" * 129, message="hello")
    with pytest.raises(ValidationError):
        ChatRequest(user_id="user", session_id="session", message="x" * 4001)


def test_chat_request_accepts_bounded_browser_coordinates():
    request = ChatRequest(
        user_id="user",
        session_id="session",
        message="Find food near me",
        latitude=1.2903,
        longitude=103.8519,
        location_label="City Hall",
    )

    assert request.latitude == 1.2903
    assert request.location_label == "City Hall"


def test_chat_request_rejects_partial_or_non_singapore_coordinates():
    with pytest.raises(ValidationError):
        ChatRequest(
            user_id="user",
            session_id="session",
            message="Find food near me",
            latitude=1.2903,
        )

    with pytest.raises(ValidationError):
        ChatRequest(
            user_id="user",
            session_id="session",
            message="Find food near me",
            latitude=40.7128,
            longitude=-74.006,
        )


def test_cors_defaults_to_base44_and_supports_explicit_allowlist(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert configured_allowed_origins() == [
        "https://aug9.sg",
        "https://www.aug9.sg",
        "https://aug-nudge-now.base44.app",
    ]


def test_admin_endpoint_authentication_is_fail_closed(monkeypatch):
    monkeypatch.setenv("AUG9_ADMIN_API_KEY", "admin-" + "x" * 32)

    assert require_admin("admin-" + "x" * 32) == "base44_admin"

    with pytest.raises(Exception) as error:
        require_admin("incorrect-" + "x" * 32)
    assert error.value.status_code == 401


def test_admin_hawker_lookup_uses_canonical_entity_search(monkeypatch):
    monkeypatch.setenv("AUG9_ADMIN_API_KEY", "admin-" + "x" * 32)

    class StubRepository:
        def search_entities(self, query, *, entity_type, limit):
            assert query == "maxwell"
            assert entity_type == "hawker_centre"
            assert limit == 25
            return []

    monkeypatch.setattr("aug9.api.main.DiscoveryRepository", StubRepository)

    assert list_hawker_centres(
        query="maxwell",
        limit=25,
        x_aug9_admin_key="admin-" + "x" * 32,
    ) == []

    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://aug-nudge-now.base44.app, https://staging.example",
    )
    assert configured_allowed_origins() == [
        "https://aug-nudge-now.base44.app",
        "https://staging.example",
    ]
