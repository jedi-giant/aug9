from aug9.core import database


def test_postgres_connection_has_bounded_timeouts(monkeypatch):
    captured = {}
    sentinel = object()

    def connect(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return sentinel

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/aug9")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("DATABASE_STATEMENT_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("DATABASE_LOCK_TIMEOUT_SECONDS", "8")
    monkeypatch.setattr(database.psycopg, "connect", connect)

    result = database.get_connection()

    assert result is sentinel
    assert captured["connect_timeout"] == 7
    assert captured["application_name"] == "aug9"
    assert "statement_timeout=45000" in captured["options"]
    assert "lock_timeout=8000" in captured["options"]
