from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from aug9.core import database
from aug9.core.operational_health import build_operational_health_report
from aug9.core.product_analytics_report import build_product_analytics_report


def build_analytics_dashboard(
    *, days: int = 7, now: datetime | None = None
) -> dict[str, Any]:
    """Build the aggregate, prompt-free payload used by the admin dashboard."""
    if days < 1 or days > 90:
        raise ValueError("dashboard days must be between 1 and 90")

    period_end = now or datetime.now(UTC)
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=UTC)
    period_start = period_end - timedelta(days=days)
    query_start: object = (
        period_start
        if database.is_postgres()
        else period_start.isoformat(sep=" ")
    )
    query_end: object = period_end if database.is_postgres() else period_end.isoformat(sep=" ")

    conn = database.get_connection()
    cursor = conn.cursor()
    p = database.placeholder()
    cursor.execute(
        f"""
        SELECT task_id, event_type, capabilities, task_status, action_type,
               helpful, feedback_scope, reason_code, journey_type,
               journey_status, failure_stage, created_at
        FROM product_events
        WHERE created_at >= {p} AND created_at < {p}
        ORDER BY created_at
        """,
        (query_start, query_end),
    )
    product_rows = cursor.fetchall()
    cursor.execute(
        f"""
        SELECT status, latency_ms, error_type, created_at
        FROM usage_events
        WHERE created_at >= {p} AND created_at < {p}
        ORDER BY created_at
        """,
        (query_start, query_end),
    )
    usage_rows = cursor.fetchall()
    conn.close()

    event_counts = Counter(str(row[1]) for row in product_rows)
    selected_tasks = {
        row[0]
        for row in product_rows
        if row[0] and row[4] in {"journey_stop_selected", "journey_stop_replaced"}
    }
    action_tasks = {
        row[0]
        for row in product_rows
        if row[0] and row[1] == "action_click"
    }
    completed_tasks = {
        row[0]
        for row in product_rows
        if row[0]
        and (
            row[1] == "task_completed"
            or row[3] == "completed"
            or (row[1] == "feedback" and bool(row[5]))
        )
    }
    funnel = [
        {"stage": "Landing views", "count": event_counts["landing_view"]},
        {"stage": "Queries", "count": event_counts["query_submitted"]},
        {"stage": "Results", "count": event_counts["result_generated"]},
        {"stage": "Cards selected", "count": len(selected_tasks)},
        {"stage": "Actions", "count": len(action_tasks)},
        {"stage": "Completed", "count": len(completed_tasks)},
    ]

    journey_statuses: Counter[str] = Counter()
    journey_types: Counter[str] = Counter()
    failure_stages: Counter[str] = Counter()
    feedback_reasons: Counter[str] = Counter()
    for row in product_rows:
        if row[8]:
            journey_types[str(row[8])] += 1
        if row[9]:
            journey_statuses[str(row[9])] += 1
        if row[10]:
            failure_stages[str(row[10])] += 1
        if row[1] == "feedback" and not bool(row[5]) and row[7]:
            feedback_reasons[str(row[7])] += 1

    daily: dict[date, Counter[str]] = defaultdict(Counter)
    for row in product_rows:
        day = _as_datetime(row[11]).date()
        daily[day][str(row[1])] += 1
    trends = []
    for offset in range(days - 1, -1, -1):
        day = period_end.date() - timedelta(days=offset)
        counts = daily[day]
        trends.append({
            "date": day.isoformat(),
            "queries": counts["query_submitted"],
            "results": counts["result_generated"],
            "actions": counts["action_click"],
            "feedback": counts["feedback"],
        })

    latencies = sorted(
        int(row[1])
        for row in usage_rows
        if row[0] == "success" and row[1] is not None
    )
    errors = Counter(
        str(row[2] or row[0]) for row in usage_rows if row[0] != "success"
    )

    return {
        "generated_at": period_end.isoformat(),
        "period_days": days,
        "product": build_product_analytics_report(days=days, now=period_end).to_dict(),
        "funnel": funnel,
        "trends": trends,
        "latency": {
            "samples": len(latencies),
            "median_ms": _percentile(latencies, 0.5),
            "p95_ms": _percentile(latencies, 0.95),
            "maximum_ms": max(latencies) if latencies else None,
        },
        "journeys": {
            "by_type": dict(journey_types.most_common()),
            "by_status": dict(journey_statuses.most_common()),
            "failure_stages": dict(failure_stages.most_common()),
        },
        "feedback_reasons": dict(feedback_reasons.most_common()),
        "request_errors": dict(errors.most_common()),
        "operations": build_operational_health_report(now=period_end),
    }


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    index = round((len(values) - 1) * percentile)
    return values[index]


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
