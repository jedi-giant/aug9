import argparse
import json

from aug9.core.operational_health import build_operational_health_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Report provider and import health")
    parser.add_argument("--stale-after-hours", type=int, default=36)
    parser.add_argument("--fail-unhealthy", action="store_true")
    args = parser.parse_args()
    report = build_operational_health_report(
        stale_after_hours=args.stale_after_hours
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_unhealthy and not report["healthy"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
