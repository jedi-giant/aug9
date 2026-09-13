import httpx
import json

from aug9.core.production_smoke import run_production_smoke


def test_production_smoke_covers_frontend_session_and_chat():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/visitor/session":
            return httpx.Response(200, json={"visitor_token": "signed-token"})
        if request.url.path == "/chat":
            body = json.loads(request.content)
            if body.get("location_label") == "Meyer Road Playground":
                return httpx.Response(200, json={
                    "response": "A nearby family outing.",
                    "metadata": {
                        "journey": {"resolved_slots": {
                            "origin": {"name": "Meyer Road Playground"}
                        }},
                        "skills": {
                            "food": {"places": [{"distance_km": 0.4}]},
                            "events": {"events": [{"distance_km": 1.8}]},
                        },
                    },
                })
            return httpx.Response(200, json={"response": "Sunny with showers."})
        return httpx.Response(200, json={"status": "ready"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report = run_production_smoke(
        "https://api.example.test", "https://app.example.test", client=client
    )

    assert report["healthy"] is True
    assert [check["name"] for check in report["checks"]] == [
        "frontend", "api", "database", "visitor_session", "chat",
        "anchored_outing",
    ]


def test_production_smoke_fails_when_chat_is_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/visitor/session":
            return httpx.Response(200, json={"visitor_token": "signed-token"})
        if request.url.path == "/chat":
            return httpx.Response(200, json={"response": ""})
        return httpx.Response(200, json={})

    report = run_production_smoke(
        "https://api.example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert report["healthy"] is False
    chat = next(check for check in report["checks"] if check["name"] == "chat")
    assert chat["detail"] == "empty_response"


def test_production_smoke_fails_when_anchored_outing_exceeds_radius():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/visitor/session":
            return httpx.Response(200, json={"visitor_token": "signed-token"})
        if request.url.path == "/chat":
            body = json.loads(request.content)
            if body.get("location_label") == "Meyer Road Playground":
                return httpx.Response(200, json={
                    "response": "A family outing.",
                    "metadata": {
                        "journey": {"resolved_slots": {
                            "origin": {"name": "Meyer Road Playground"}
                        }},
                        "skills": {
                            "food": {"places": [{"distance_km": 0.4}]},
                            "events": {"events": [{"distance_km": 3.6}]},
                        },
                    },
                })
            return httpx.Response(200, json={"response": "Cloudy."})
        return httpx.Response(200, json={})

    report = run_production_smoke(
        "https://api.example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    check = next(
        item for item in report["checks"] if item["name"] == "anchored_outing"
    )
    assert report["healthy"] is False
    assert check["detail"] == "spatial_policy_failed"
