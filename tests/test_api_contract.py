import pytest
from pydantic import ValidationError

from aug9.api.main import ChatRequest, ChatResponse, configured_allowed_origins


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


def test_cors_defaults_to_base44_and_supports_explicit_allowlist(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert configured_allowed_origins() == ["https://aug-nudge-now.base44.app"]

    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://aug-nudge-now.base44.app, https://staging.example",
    )
    assert configured_allowed_origins() == [
        "https://aug-nudge-now.base44.app",
        "https://staging.example",
    ]
