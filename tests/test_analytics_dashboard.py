from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.core.analytics_dashboard import build_analytics_dashboard
from aug9.core.product_analytics import (
    ProductEvent,
    ProductEventType,
    TaskStatus,
    log_product_event,
)


@pytest.fixture(autouse=True)
def analytics_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "dashboard.db")
    for name in (
        "OPENAI_API_KEY",
        "ONEMAP_BASE_URL",
        "ONEMAP_EMAIL",
        "ONEMAP_PASSWORD",
    ):
        monkeypatch.setenv(name, "configured")
    database.initialise_database()


def test_builds_prompt_free_dashboard_payload():
    for event in (
        ProductEvent(
            event_id="landing", user_id="user", event_type=ProductEventType.LANDING_VIEW
        ),
        ProductEvent(
            event_id="query", task_id="task", user_id="user",
            event_type=ProductEventType.QUERY_SUBMITTED,
            capabilities=["food"],
        ),
        ProductEvent(
            event_id="result", task_id="task", user_id="user",
            event_type=ProductEventType.RESULT_GENERATED,
            capabilities=["food"], task_status=TaskStatus.ANSWER_GENERATED,
            journey_type="day", journey_status="ready",
        ),
        ProductEvent(
            event_id="selected", task_id="task", user_id="user",
            event_type=ProductEventType.ACTION_CLICK,
            action_type="journey_stop_selected",
        ),
        ProductEvent(
            event_id="feedback", task_id="task", user_id="user",
            event_type=ProductEventType.FEEDBACK, helpful=False,
            feedback_scope="card", reason_code="too_far",
        ),
    ):
        log_product_event(event)
    database.log_usage_event(
        user_id="user", session_id="session", message_length=20,
        status="success", latency_ms=1200,
    )

    report = build_analytics_dashboard(days=7, now=datetime.now(UTC))

    assert report["product"]["queries_submitted"] == 1
    assert report["latency"]["median_ms"] == 1200
    assert report["journeys"]["by_status"] == {"ready": 1}
    assert report["feedback_reasons"] == {"too_far": 1}
    selected = next(
        item for item in report["funnel"] if item["stage"] == "Cards selected"
    )
    assert selected["count"] == 1
    assert len(report["trends"]) == 7


def test_rejects_oversized_dashboard_window():
    with pytest.raises(ValueError, match="between 1 and 90"):
        build_analytics_dashboard(days=91)
