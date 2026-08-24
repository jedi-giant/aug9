from aug9.core.database import (
    get_connection,
    initialise_database,
    log_usage_event,
)


def test_usage_event_is_logged():

    initialise_database()

    log_usage_event(
        user_id="test_user",
        session_id="test_session",
        message_length=42,
        status="success",
        latency_ms=123,
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            user_id,
            session_id,
            message_length,
            status,
            latency_ms
        FROM usage_events
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        ("test_user",),
    )

    row = cursor.fetchone()

    conn.close()

    assert row == (
        "test_user",
        "test_session",
        42,
        "success",
        123,
    )
