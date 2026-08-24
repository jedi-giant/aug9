from datetime import datetime, timedelta, timezone

import pytest

from aug9.api.rate_limit import (
    RateLimitExceeded,
    RateLimiter,
)


def test_rate_limiter_allows_requests_under_limit():

    limiter = RateLimiter()

    for _ in range(5):
        limiter.check(
            "test_user"
        )


def test_rate_limiter_blocks_sixth_request():

    limiter = RateLimiter()

    for _ in range(5):
        limiter.check(
            "test_user"
        )

    with pytest.raises(
        RateLimitExceeded
    ):
        limiter.check(
            "test_user"
        )


def test_rate_limits_users_independently():

    limiter = RateLimiter()

    for _ in range(5):
        limiter.check(
            "user_a"
        )

    # User B should remain unaffected.
    limiter.check(
        "user_b"
    )


def test_old_requests_are_removed():

    limiter = RateLimiter()

    old_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(days=2)
    )

    limiter._requests["test_user"].append(
        old_timestamp
    )

    limiter.check(
        "test_user"
    )

    assert len(
        limiter._requests["test_user"]
    ) == 1
