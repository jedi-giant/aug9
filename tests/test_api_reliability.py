import pytest
from fastapi import HTTPException

from aug9.api import main
from aug9.core.agent_response import AgentResponse


def test_readiness_reports_database_availability(monkeypatch):
    monkeypatch.setattr(main, "database_is_ready", lambda: True)

    assert main.readiness_check() == {"status": "ready"}


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(main, "database_is_ready", lambda: False)

    with pytest.raises(HTTPException) as error:
        main.readiness_check()

    assert error.value.status_code == 503
    assert error.value.detail["dependency"] == "database"


def test_chat_succeeds_when_usage_analytics_write_fails(monkeypatch):
    monkeypatch.setattr(main.rate_limiter, "check", lambda user_id: None)
    monkeypatch.setattr(
        main,
        "run_aug9",
        lambda *args, **kwargs: AgentResponse(response="Useful answer"),
    )
    monkeypatch.setattr(
        main,
        "log_usage_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("analytics unavailable")),
    )
    monkeypatch.setattr(main, "try_log_product_event", lambda event: False)

    response = main.chat(
        main.ChatRequest(user_id="user", session_id="session", message="Hello")
    )

    assert response.response == "Useful answer"


def test_chat_returns_stable_503_for_unexpected_dependency_failure(monkeypatch):
    monkeypatch.setattr(main.rate_limiter, "check", lambda user_id: None)
    monkeypatch.setattr(
        main,
        "run_aug9",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    monkeypatch.setattr(main, "log_usage_event", lambda **kwargs: None)

    with pytest.raises(HTTPException) as error:
        main.chat(
            main.ChatRequest(user_id="user", session_id="session", message="Hello")
        )

    assert error.value.status_code == 503
    assert error.value.detail["error"] == "temporarily_unavailable"
    assert "provider down" not in error.value.detail["message"]
