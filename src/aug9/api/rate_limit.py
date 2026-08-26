from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock


REQUESTS_PER_MINUTE = 5
REQUESTS_PER_DAY = 100


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Rate limit exceeded")


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int = REQUESTS_PER_MINUTE,
        requests_per_day: int = REQUESTS_PER_DAY,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self._requests: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)

        minute_cutoff = now - timedelta(minutes=1)
        day_cutoff = now - timedelta(days=1)

        with self._lock:
            requests = self._requests[user_id]

            # Remove anything older than 24 hours.
            while requests and requests[0] < day_cutoff:
                requests.popleft()

            requests_last_day = len(requests)

            requests_last_minute = sum(
                1
                for timestamp in requests
                if timestamp >= minute_cutoff
            )

            if requests_last_minute >= self.requests_per_minute:
                oldest_recent = next(
                    timestamp
                    for timestamp in requests
                    if timestamp >= minute_cutoff
                )

                retry_after = (
                    oldest_recent
                    + timedelta(minutes=1)
                    - now
                ).total_seconds()

                raise RateLimitExceeded(
                    retry_after_seconds=max(
                        1,
                        int(retry_after) + 1,
                    )
                )

            if requests_last_day >= self.requests_per_day:
                retry_after = (
                    requests[0]
                    + timedelta(days=1)
                    - now
                ).total_seconds()

                raise RateLimitExceeded(
                    retry_after_seconds=max(
                        1,
                        int(retry_after) + 1,
                    )
                )

            requests.append(now)


rate_limiter = RateLimiter()
visitor_session_rate_limiter = RateLimiter(
    requests_per_minute=30,
    requests_per_day=500,
)
product_event_rate_limiter = RateLimiter(
    requests_per_minute=60,
    requests_per_day=2000,
)
