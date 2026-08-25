from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.core.product_analytics import (
    ProductEvent,
    ProductEventType,
    log_product_event,
)
from aug9.core.product_analytics_report import build_product_analytics_report


@pytest.fixture(autouse=True)
def analytics_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "analytics.db")
    database.initialise_database()


def log(event_type, *, event_id, task_id=None, user_id="user-1", **kwargs):
    log_product_event(
        ProductEvent(
            event_id=event_id,
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            **kwargs,
        )
    )


def test_builds_prompt_free_activation_report():
    log(ProductEventType.LANDING_VIEW, event_id="landing")
    log(
        ProductEventType.QUERY_SUBMITTED,
        event_id="query-1",
        task_id="task-1",
        capabilities=["hawkers", "place_resolution"],
        campaign_source="linkedin",
    )
    log(
        ProductEventType.RESULT_GENERATED,
        event_id="result-1",
        task_id="task-1",
    )
    log(
        ProductEventType.ACTION_CLICK,
        event_id="action-1",
        task_id="task-1",
    )
    log(
        ProductEventType.FEEDBACK,
        event_id="feedback-1",
        task_id="task-1",
        helpful=True,
    )
    log(
        ProductEventType.QUERY_SUBMITTED,
        event_id="query-2",
        task_id="task-2",
        user_id="user-2",
        capabilities=["weather"],
    )

    report = build_product_analytics_report(
        days=7,
        now=datetime.now(UTC),
    )

    assert report.landing_views == 1
    assert report.queries_submitted == 2
    assert report.results_generated == 1
    assert report.successful_tasks == 1
    assert report.active_users == 2
    assert report.first_query_conversion_rate == 1.0
    assert report.successful_task_rate == 0.5
    assert report.action_click_rate == 1.0
    assert report.positive_feedback_rate == 1.0
    assert report.capability_demand == {
        "hawkers": 1,
        "place_resolution": 1,
        "weather": 1,
    }
    assert report.campaign_sources == {"linkedin": 1}


def test_empty_report_uses_null_rates():
    report = build_product_analytics_report(
        now=datetime(2030, 1, 2, tzinfo=UTC)
    )

    assert report.queries_submitted == 0
    assert report.successful_task_rate is None
    assert report.first_query_conversion_rate is None


def test_rejects_invalid_reporting_window():
    with pytest.raises(ValueError, match="between 1 and 366"):
        build_product_analytics_report(days=0)
