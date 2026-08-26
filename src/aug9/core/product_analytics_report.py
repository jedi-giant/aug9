import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from aug9.core import database


@dataclass(frozen=True)
class ProductAnalyticsReport:
    period_days: int
    period_start: str
    period_end: str
    landing_views: int
    queries_submitted: int
    results_generated: int
    successful_tasks: int
    active_users: int
    first_query_conversion_rate: float | None
    successful_task_rate: float | None
    action_click_rate: float | None
    positive_feedback_rate: float | None
    capability_demand: dict[str, int]
    failed_results_by_capability: dict[str, int]
    capability_result_success_rate: dict[str, float | None]
    campaign_sources: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def build_product_analytics_report(
    *,
    days: int = 7,
    now: datetime | None = None,
) -> ProductAnalyticsReport:
    if days < 1 or days > 366:
        raise ValueError("days must be between 1 and 366")

    period_end = now or datetime.now(UTC)
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=UTC)
    period_start = period_end - timedelta(days=days)

    if database.is_postgres():
        query_period_start = period_start
        query_period_end = period_end
    else:
        query_period_start = period_start.isoformat(sep=" ")
        query_period_end = period_end.isoformat(sep=" ")

    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    cursor.execute(
        f"""
        SELECT
            task_id,
            user_id,
            event_type,
            capabilities,
            helpful,
            campaign_source,
            task_status
        FROM product_events
        WHERE created_at >= {p}
          AND created_at < {p}
        """,
        (query_period_start, query_period_end),
    )
    rows = cursor.fetchall()
    conn.close()

    events_by_type = Counter(row[2] for row in rows)
    query_users = {row[1] for row in rows if row[2] == "query_submitted"}
    landing_users = {row[1] for row in rows if row[2] == "landing_view"}
    successful_task_ids = {
        row[0]
        for row in rows
        if row[0]
        and (
            row[2] in {"action_click", "task_completed"}
            or (row[2] == "feedback" and bool(row[4]))
        )
    }
    submitted_task_ids = {
        row[0] for row in rows if row[0] and row[2] == "query_submitted"
    }

    capabilities: Counter[str] = Counter()
    failed_capabilities: Counter[str] = Counter()
    campaigns: Counter[str] = Counter()
    for row in rows:
        if row[2] == "result_generated":
            try:
                event_capabilities = json.loads(row[3] or "[]")
                capabilities.update(event_capabilities)
                if row[6] == "failed":
                    failed_capabilities.update(event_capabilities)
            except (json.JSONDecodeError, TypeError):
                continue
        if row[2] == "query_submitted":
            if row[5]:
                campaigns[row[5]] += 1

    feedback_rows = [row for row in rows if row[2] == "feedback"]
    positive_feedback = sum(bool(row[4]) for row in feedback_rows)
    action_clicks = events_by_type["action_click"]
    results_generated = events_by_type["result_generated"]

    return ProductAnalyticsReport(
        period_days=days,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        landing_views=events_by_type["landing_view"],
        queries_submitted=events_by_type["query_submitted"],
        results_generated=results_generated,
        successful_tasks=len(successful_task_ids),
        active_users=len(query_users),
        first_query_conversion_rate=_rate(
            len(query_users & landing_users),
            len(landing_users),
        ),
        successful_task_rate=_rate(
            len(successful_task_ids & submitted_task_ids),
            len(submitted_task_ids),
        ),
        action_click_rate=_rate(action_clicks, results_generated),
        positive_feedback_rate=_rate(positive_feedback, len(feedback_rows)),
        capability_demand=dict(capabilities.most_common()),
        failed_results_by_capability=dict(failed_capabilities.most_common()),
        capability_result_success_rate={
            capability: _rate(count - failed_capabilities[capability], count)
            for capability, count in capabilities.most_common()
        },
        campaign_sources=dict(campaigns.most_common()),
    )
