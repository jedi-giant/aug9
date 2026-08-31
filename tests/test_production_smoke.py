import httpx

from aug9.core.production_smoke import run_production_smoke


def test_production_smoke_covers_frontend_session_and_chat():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/visitor/session":
            return httpx.Response(200, json={"visitor_token": "signed-token"})
        if request.url.path == "/chat":
            return httpx.Response(200, json={"response": "Sunny with showers."})
        return httpx.Response(200, json={"status": "ready"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report = run_production_smoke(
        "https://api.example.test", "https://app.example.test", client=client
    )

    assert report["healthy"] is True
    assert [check["name"] for check in report["checks"]] == [
        "frontend", "api", "database", "visitor_session", "chat"
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
    assert report["checks"][-1]["detail"] == "empty_response"
