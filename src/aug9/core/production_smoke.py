import argparse
import json
import time
from dataclasses import dataclass
from uuid import uuid4

import httpx


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    healthy: bool
    status_code: int | None
    latency_ms: int
    detail: str


def run_production_smoke(
    api_url: str,
    frontend_url: str = "https://aug9.sg",
    *,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    owned_client = client is None
    http = client or httpx.Client(timeout=20, follow_redirects=True)
    checks: list[SmokeCheck] = []

    def request(name: str, method: str, url: str, **kwargs) -> httpx.Response | None:
        started = time.perf_counter()
        try:
            response = http.request(method, url, **kwargs)
            checks.append(SmokeCheck(
                name, response.is_success, response.status_code,
                int((time.perf_counter() - started) * 1000),
                "ok" if response.is_success else "unexpected_status",
            ))
            return response
        except httpx.HTTPError as error:
            checks.append(SmokeCheck(
                name, False, None,
                int((time.perf_counter() - started) * 1000),
                error.__class__.__name__,
            ))
            return None

    try:
        request("frontend", "GET", frontend_url)
        request("api", "GET", api_url.rstrip("/") + "/")
        request("database", "GET", api_url.rstrip("/") + "/health/ready")
        visitor = request(
            "visitor_session", "POST",
            api_url.rstrip("/") + "/visitor/session",
        )
        token = visitor.json().get("visitor_token") if visitor and visitor.is_success else None
        if token:
            chat = request(
                "chat", "POST", api_url.rstrip("/") + "/chat",
                json={
                    "user_id": "production-smoke",
                    "session_id": f"smoke-{uuid4()}",
                    "message": "What is the weather in Singapore today?",
                    "visitor_token": token,
                },
            )
            if chat and chat.is_success and not chat.json().get("response"):
                prior = checks.pop()
                checks.append(SmokeCheck(
                    prior.name, False, prior.status_code, prior.latency_ms,
                    "empty_response",
                ))
        else:
            checks.append(SmokeCheck("chat", False, None, 0, "no_visitor_token"))
    finally:
        if owned_client:
            http.close()

    return {
        "healthy": all(check.healthy for check in checks),
        "checks": [check.__dict__ for check in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the deployed Aug9 journey")
    parser.add_argument(
        "--api-url", default="https://aug9-production.up.railway.app"
    )
    parser.add_argument("--frontend-url", default="https://aug9.sg")
    args = parser.parse_args()
    report = run_production_smoke(args.api_url, args.frontend_url)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["healthy"] else 1)


if __name__ == "__main__":
    main()
