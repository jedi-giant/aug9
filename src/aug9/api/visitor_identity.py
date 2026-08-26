import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from uuid import uuid4


VISITOR_TOKEN_LIFETIME_SECONDS = 90 * 24 * 60 * 60


class VisitorTokenError(ValueError):
    pass


class VisitorTokenConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisitorIdentity:
    user_id: str
    rate_limit_key: str
    token: str | None
    verified: bool


def issue_visitor_token(now: int | None = None) -> str:
    secret = _secret(required=True)
    issued_at = int(time.time() if now is None else now)
    payload = {
        "v": 1,
        "sub": str(uuid4()),
        "iat": issued_at,
        "exp": issued_at + VISITOR_TOKEN_LIFETIME_SECONDS,
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(encoded, secret)
    return f"{encoded}.{signature}"


def verify_visitor_token(token: str, now: int | None = None) -> dict:
    secret = _secret(required=True)
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = _sign(encoded, secret)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise VisitorTokenError("Invalid visitor token")
        payload = json.loads(_decode(encoded))
        current_time = int(time.time() if now is None else now)
        if payload.get("v") != 1 or not payload.get("sub"):
            raise VisitorTokenError("Invalid visitor token")
        if int(payload.get("exp", 0)) <= current_time:
            raise VisitorTokenError("Visitor token has expired")
    except VisitorTokenError:
        raise
    except (binascii.Error, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise VisitorTokenError("Invalid visitor token") from exc
    return payload


def resolve_visitor_identity(
    token: str | None,
    legacy_user_id: str,
) -> VisitorIdentity:
    secret = _secret(required=False)
    require_token = os.getenv("REQUIRE_VISITOR_TOKEN", "false").casefold() in {
        "1",
        "true",
        "yes",
    }
    if token:
        if secret is None:
            raise VisitorTokenConfigurationError(
                "Visitor token verification is not configured"
            )
        payload = verify_visitor_token(token)
        subject = str(payload["sub"])
        return VisitorIdentity(
            user_id=f"visitor:{subject}",
            rate_limit_key=f"visitor:{subject}",
            token=token,
            verified=True,
        )
    if require_token:
        raise VisitorTokenError("Visitor token is required")
    issued_token = issue_visitor_token() if secret is not None else None
    return VisitorIdentity(
        user_id=legacy_user_id,
        rate_limit_key=f"legacy:{legacy_user_id}",
        token=issued_token,
        verified=False,
    )


def _secret(*, required: bool) -> bytes | None:
    value = os.getenv("AUG9_VISITOR_TOKEN_SECRET", "")
    if not value:
        if required:
            raise VisitorTokenConfigurationError(
                "AUG9_VISITOR_TOKEN_SECRET is not configured"
            )
        return None
    if len(value) < 32:
        raise VisitorTokenConfigurationError(
            "AUG9_VISITOR_TOKEN_SECRET must contain at least 32 characters"
        )
    return value.encode()


def _sign(encoded_payload: str, secret: bytes) -> str:
    digest = hmac.new(secret, encoded_payload.encode(), hashlib.sha256).digest()
    return _encode(digest)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
