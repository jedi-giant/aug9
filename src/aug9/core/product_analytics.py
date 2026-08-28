import json
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from aug9.core import database


class ProductEventType(StrEnum):
    LANDING_VIEW = "landing_view"
    QUERY_SUBMITTED = "query_submitted"
    RESULT_GENERATED = "result_generated"
    ACTION_CLICK = "action_click"
    FEEDBACK = "feedback"
    SHARE = "share"
    TASK_COMPLETED = "task_completed"


class TaskStatus(StrEnum):
    STARTED = "started"
    ANSWER_GENERATED = "answer_generated"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), max_length=80)
    task_id: str | None = Field(default=None, max_length=80)
    user_id: str = Field(min_length=1, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    event_type: ProductEventType
    capabilities: list[str] = Field(default_factory=list, max_length=10)
    task_status: TaskStatus | None = None
    action_type: str | None = Field(default=None, max_length=80)
    helpful: bool | None = None
    campaign_source: str | None = Field(default=None, max_length=120)
    campaign_medium: str | None = Field(default=None, max_length=120)
    campaign_name: str | None = Field(default=None, max_length=120)
    ranking_mode: str | None = Field(default=None, max_length=30)

    @property
    def successful_task(self) -> bool:
        return (
            self.event_type == ProductEventType.TASK_COMPLETED
            or self.event_type == ProductEventType.ACTION_CLICK
            or (
                self.event_type == ProductEventType.FEEDBACK
                and self.helpful is True
            )
        )


def log_product_event(event: ProductEvent) -> None:
    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    cursor.execute(
        f"""
        INSERT INTO product_events (
            event_id, task_id, user_id, session_id, event_type, capabilities,
            task_status, action_type, helpful, successful_task,
            campaign_source, campaign_medium, campaign_name, ranking_mode
        ) VALUES (
            {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}
        )
        ON CONFLICT(event_id) DO NOTHING
        """,
        (
            event.event_id,
            event.task_id,
            event.user_id,
            event.session_id,
            event.event_type.value,
            json.dumps(event.capabilities),
            event.task_status.value if event.task_status else None,
            event.action_type,
            int(event.helpful) if event.helpful is not None else None,
            int(event.successful_task),
            event.campaign_source,
            event.campaign_medium,
            event.campaign_name,
            event.ranking_mode,
        ),
    )
    conn.commit()
    conn.close()


def try_log_product_event(event: ProductEvent) -> bool:
    """Keep optional analytics failures from breaking the user's task."""
    try:
        log_product_event(event)
        return True
    except Exception:
        return False
