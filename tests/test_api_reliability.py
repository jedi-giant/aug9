import asyncio

import pytest
from fastapi import BackgroundTasks, HTTPException

from aug9.api import main
from aug9.core.agent_response import AgentResponse
from aug9.api.visitor_identity import issue_visitor_token


VISITOR_SECRET = "test-visitor-secret-that-is-at-least-32-characters"


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

    background_tasks = BackgroundTasks()
    response = main.chat(
        main.ChatRequest(user_id="user", session_id="session", message="Hello"),
        background_tasks,
    )

    assert response.response == "Useful answer"
    assert len(background_tasks.tasks) == 2
    asyncio.run(background_tasks())


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
            main.ChatRequest(user_id="user", session_id="session", message="Hello"),
            BackgroundTasks(),
        )

    assert error.value.status_code == 503
    assert error.value.detail["error"] == "temporarily_unavailable"
    assert "provider down" not in error.value.detail["message"]


def test_verified_visitor_identity_replaces_caller_user_id(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", VISITOR_SECRET)
    token = issue_visitor_token()
    captured = {}
    monkeypatch.setattr(
        main.rate_limiter,
        "check",
        lambda key: captured.update(rate_limit_key=key),
    )

    def run_agent(*args, **kwargs):
        captured["user_id"] = kwargs["user_id"]
        return AgentResponse(response="Verified answer")

    monkeypatch.setattr(main, "run_aug9", run_agent)
    response = main.chat(
        main.ChatRequest(
            user_id="caller-controlled-id",
            session_id="session",
            message="Hello",
            visitor_token=token,
        ),
        BackgroundTasks(),
    )

    assert captured["user_id"].startswith("visitor:")
    assert captured["user_id"] != "caller-controlled-id"
    assert captured["rate_limit_key"] == captured["user_id"]
    assert response.metadata["visitor_identity_verified"] is True


def test_invalid_visitor_token_returns_401(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", VISITOR_SECRET)

    with pytest.raises(HTTPException) as error:
        main.chat(
            main.ChatRequest(
                user_id="user",
                session_id="session",
                message="Hello",
                visitor_token="invalid.token",
            ),
            BackgroundTasks(),
        )

    assert error.value.status_code == 401
    assert error.value.detail["error"] == "invalid_visitor_token"


def test_visitor_session_issues_token(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", VISITOR_SECRET)

    response = main.create_visitor_session()

    assert response.visitor_token
    assert response.expires_in_seconds > 0
