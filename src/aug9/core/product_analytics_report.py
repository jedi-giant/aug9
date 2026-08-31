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
    response_feedback_count: int
    response_positive_feedback_rate: float | None
    card_feedback_count: int
    card_positive_feedback_rate: float | None
    card_feedback_by_reason: dict[str, int]
    card_feedback_by_capability: dict[str, dict[str, int]]
    capability_demand: dict[str, int]
    failed_results_by_capability: dict[str, int]
    capability_result_success_rate: dict[str, float | None]
    campaign_sources: dict[str, int]
    ranking_modes: dict[str, int]
    ranking_mode_outcomes: dict[str, dict[str, int | float | None]]

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
            task_status,
            ranking_mode,
            feedback_scope,
            target_id,
            reason_code
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
    ranking_modes: Counter[str] = Counter()
    for row in rows:
        if row[2] == "result_generated":
            try:
                event_capabilities = json.loads(row[3] or "[]")
                capabilities.update(event_capabilities)
                if row[6] == "failed":
                    failed_capabilities.update(event_capabilities)
                if row[7]:
                    ranking_modes[row[7]] += 1
            except (json.JSONDecodeError, TypeError):
                continue
        if row[2] == "query_submitted":
            if row[5]:
                campaigns[row[5]] += 1

    feedback_rows = [row for row in rows if row[2] == "feedback"]
    positive_feedback = sum(bool(row[4]) for row in feedback_rows)
    response_feedback_rows = [row for row in feedback_rows if row[8] != "card"]
    card_feedback_rows = [row for row in feedback_rows if row[8] == "card"]
    card_feedback_reasons: Counter[str] = Counter(
        row[10] for row in card_feedback_rows if row[10]
    )
    card_feedback_by_capability: dict[str, Counter[str]] = {}
    for row in card_feedback_rows:
        try:
            feedback_capabilities = json.loads(row[3] or "[]")
        except (json.JSONDecodeError, TypeError):
            feedback_capabilities = []
        outcome = "positive" if bool(row[4]) else row[10] or "negative"
        for capability in feedback_capabilities:
            card_feedback_by_capability.setdefault(
                capability, Counter()
            )[outcome] += 1
    action_clicks = events_by_type["action_click"]
    results_generated = events_by_type["result_generated"]
    ranking_mode_by_task = {
        row[0]: row[7]
        for row in rows
        if row[0] and row[2] == "result_generated" and row[7]
    }
    action_task_ids = {
        row[0] for row in rows if row[0] and row[2] == "action_click"
    }
    feedback_by_task = {
        row[0]: bool(row[4])
        for row in rows
        if row[0] and row[2] == "feedback"
    }
    ranking_mode_outcomes = {}
    for mode in sorted(set(ranking_mode_by_task.values())):
        mode_tasks = {
            task_id
            for task_id, task_mode in ranking_mode_by_task.items()
            if task_mode == mode
        }
        mode_feedback_tasks = mode_tasks & feedback_by_task.keys()
        ranking_mode_outcomes[mode] = {
            "result_tasks": len(mode_tasks),
            "action_click_tasks": len(mode_tasks & action_task_ids),
            "successful_tasks": len(mode_tasks & successful_task_ids),
            "feedback_tasks": len(mode_feedback_tasks),
            "positive_feedback_tasks": sum(
                feedback_by_task[task_id] for task_id in mode_feedback_tasks
            ),
            "action_click_rate": _rate(
                len(mode_tasks & action_task_ids), len(mode_tasks)
            ),
            "successful_task_rate": _rate(
                len(mode_tasks & successful_task_ids), len(mode_tasks)
            ),
            "positive_feedback_rate": _rate(
                sum(feedback_by_task[task_id] for task_id in mode_feedback_tasks),
                len(mode_feedback_tasks),
            ),
        }

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
        response_feedback_count=len(response_feedback_rows),
        response_positive_feedback_rate=_rate(
            sum(bool(row[4]) for row in response_feedback_rows),
            len(response_feedback_rows),
        ),
        card_feedback_count=len(card_feedback_rows),
        card_positive_feedback_rate=_rate(
            sum(bool(row[4]) for row in card_feedback_rows),
            len(card_feedback_rows),
        ),
        card_feedback_by_reason=dict(card_feedback_reasons.most_common()),
        card_feedback_by_capability={
            capability: dict(outcomes.most_common())
            for capability, outcomes in sorted(card_feedback_by_capability.items())
        },
        capability_demand=dict(capabilities.most_common()),
        failed_results_by_capability=dict(failed_capabilities.most_common()),
        capability_result_success_rate={
            capability: _rate(count - failed_capabilities[capability], count)
            for capability, count in capabilities.most_common()
        },
        campaign_sources=dict(campaigns.most_common()),
        ranking_modes=dict(ranking_modes.most_common()),
        ranking_mode_outcomes=ranking_mode_outcomes,
    )
