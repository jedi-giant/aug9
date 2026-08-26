import pytest

from aug9.api.visitor_identity import (
    VisitorTokenConfigurationError,
    VisitorTokenError,
    issue_visitor_token,
    resolve_visitor_identity,
    verify_visitor_token,
)


SECRET = "test-visitor-secret-that-is-at-least-32-characters"


def test_signed_visitor_token_round_trip(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", SECRET)

    token = issue_visitor_token(now=1000)
    payload = verify_visitor_token(token, now=1001)

    assert payload["v"] == 1
    assert payload["exp"] > payload["iat"]


def test_tampered_and_expired_tokens_are_rejected(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", SECRET)
    token = issue_visitor_token(now=1000)

    with pytest.raises(VisitorTokenError):
        verify_visitor_token(token + "tampered", now=1001)
    with pytest.raises(VisitorTokenError, match="expired"):
        verify_visitor_token(token, now=1000 + 91 * 24 * 60 * 60)


def test_legacy_request_receives_token_then_uses_verified_identity(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", SECRET)
    monkeypatch.delenv("REQUIRE_VISITOR_TOKEN", raising=False)

    legacy = resolve_visitor_identity(None, "client-user")
    verified = resolve_visitor_identity(legacy.token, "spoofed-user")

    assert legacy.user_id == "client-user"
    assert legacy.verified is False
    assert verified.verified is True
    assert verified.user_id.startswith("visitor:")
    assert verified.user_id != "spoofed-user"


def test_required_token_rejects_legacy_identity(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", SECRET)
    monkeypatch.setenv("REQUIRE_VISITOR_TOKEN", "true")

    with pytest.raises(VisitorTokenError, match="required"):
        resolve_visitor_identity(None, "legacy")


def test_short_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("AUG9_VISITOR_TOKEN_SECRET", "short")

    with pytest.raises(VisitorTokenConfigurationError):
        issue_visitor_token()
