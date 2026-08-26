from aug9.discovery import refresh_events


def test_daily_refresh_imports_before_archiving(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        refresh_events, "import_public_events", lambda: calls.append("import")
    )
    monkeypatch.setattr(
        refresh_events,
        "enrich_event_venues",
        lambda: calls.append("enrich"),
    )
    monkeypatch.setattr(
        refresh_events,
        "archive_expired_events",
        lambda: calls.append("archive"),
    )

    refresh_events.main()

    assert calls == ["import", "enrich", "archive"]
    output = capsys.readouterr().out
    assert "Daily event refresh starting" in output
    assert "Daily event refresh complete" in output
