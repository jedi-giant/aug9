import json

import pytest

from aug9.core import database
from aug9.core.product_analytics import (
    ProductEvent,
    ProductEventType,
    TaskStatus,
    log_product_event,
)


@pytest.fixture(autouse=True)
def analytics_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "analytics.db")
    database.initialise_database()


def test_action_click_counts_as_successful_task_and_is_idempotent():
    event = ProductEvent(
        event_id="event-1",
        task_id="task-1",
        user_id="anon-user",
        session_id="session-1",
        event_type=ProductEventType.ACTION_CLICK,
        capabilities=["hotels"],
        task_status=TaskStatus.COMPLETED,
        action_type="open_url",
        campaign_source="linkedin",
    )

    log_product_event(event)
    log_product_event(event)

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT event_type, capabilities, successful_task, campaign_source
        FROM product_events
        """
    )
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0] == (
        "action_click",
        json.dumps(["hotels"]),
        1,
        "linkedin",
    )


def test_positive_feedback_counts_as_successful_task():
    event = ProductEvent(
        task_id="task-2",
        user_id="anon-user",
        event_type=ProductEventType.FEEDBACK,
        helpful=True,
    )

    assert event.successful_task is True


def test_generated_result_is_not_task_completion():
    event = ProductEvent(
        task_id="task-3",
        user_id="anon-user",
        event_type=ProductEventType.RESULT_GENERATED,
        task_status=TaskStatus.ANSWER_GENERATED,
    )

    assert event.successful_task is False


def test_result_event_records_food_ranking_mode():
    log_product_event(
        ProductEvent(
            task_id="task-ranking",
            user_id="anon-user",
            event_type=ProductEventType.RESULT_GENERATED,
            capabilities=["food"],
            ranking_mode="shortlist",
        )
    )

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ranking_mode FROM product_events WHERE task_id = 'task-ranking'"
    )
    assert cursor.fetchone()[0] == "shortlist"
    conn.close()


def test_result_event_records_bounded_journey_outcome():
    log_product_event(
        ProductEvent(
            task_id="task-journey",
            user_id="visitor-journey",
            session_id="session-journey",
            event_type=ProductEventType.RESULT_GENERATED,
            journey_type="day",
            journey_status="partial",
            failure_stage="transport",
        )
    )

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT journey_type, journey_status, failure_stage "
        "FROM product_events WHERE task_id = 'task-journey'"
    )
    assert cursor.fetchone() == ("day", "partial", "transport")
    conn.close()


def test_card_feedback_records_target_and_reason():
    log_product_event(
        ProductEvent(
            task_id="task-card-feedback",
            user_id="anon-user",
            event_type=ProductEventType.FEEDBACK,
            capabilities=["food"],
            helpful=False,
            feedback_scope="card",
            target_id="food:sfa:123",
            reason_code="lost_context",
        )
    )

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT feedback_scope, target_id, reason_code
           FROM product_events WHERE task_id = 'task-card-feedback'"""
    )
    assert cursor.fetchone() == ("card", "food:sfa:123", "lost_context")
    conn.close()
