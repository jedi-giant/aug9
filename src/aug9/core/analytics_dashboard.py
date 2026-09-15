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
               journey_status, failure_stage, created_at, user_id,
               campaign_source
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
    product = build_product_analytics_report(days=days, now=period_end).to_dict()
    query_users = Counter(
        str(row[12])
        for row in product_rows
        if row[1] == "query_submitted" and row[12]
    )
    structured_beta_users = {
        str(row[12])
        for row in product_rows
        if row[12]
        and str(row[13] or "").casefold() in {"beta", "structured_beta"}
    }
    result_tasks = {
        str(row[0]) for row in product_rows
        if row[0] and row[1] == "result_generated"
    }
    feedback_tasks = {
        str(row[0]) for row in product_rows
        if row[0] and row[1] == "feedback"
    }
    lost_context_count = feedback_reasons["lost_context"]
    query_count = event_counts["query_submitted"]
    feedback_coverage = (
        len(feedback_tasks) / len(result_tasks) if result_tasks else 0.0
    )
    context_loss_rate = lost_context_count / query_count if query_count else 0.0
    p95_latency = _percentile(latencies, 0.95)
    gates = [
        _gate("Tester sample", len(query_users), 20, len(query_users) >= 20),
        _gate(
            "Feedback coverage", feedback_coverage, 0.25,
            feedback_coverage >= 0.25,
        ),
        _gate(
            "Task success", product["successful_task_rate"], 0.60,
            product["successful_task_rate"] >= 0.60,
        ),
        _gate(
            "P95 response", p95_latency, 8_000,
            p95_latency is not None and p95_latency <= 8_000,
            direction="maximum",
        ),
        _gate(
            "Lost context", context_loss_rate, 0.10,
            context_loss_rate <= 0.10,
            direction="maximum",
        ),
    ]

    return {
        "generated_at": period_end.isoformat(),
        "period_days": days,
        "product": product,
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
        "beta_health": {
            "status": "ready" if all(gate["passed"] for gate in gates) else "collecting",
            "testers": len(query_users),
            "structured_beta_testers": len(structured_beta_users),
            "repeat_testers": sum(count >= 2 for count in query_users.values()),
            "journeys_attempted": sum(journey_types.values()),
            "journeys_ready": journey_statuses["ready"],
            "feedback_coverage_rate": round(feedback_coverage, 4),
            "lost_context_count": lost_context_count,
            "lost_context_rate": round(context_loss_rate, 4),
            "gates": gates,
        },
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


def _gate(
    name: str,
    current: int | float | None,
    target: int | float,
    passed: bool,
    *,
    direction: str = "minimum",
) -> dict[str, Any]:
    return {
        "name": name,
        "current": current,
        "target": target,
        "direction": direction,
        "passed": passed,
    }
