import argparse
import json

from aug9.core.database import initialise_database
from aug9.core.product_analytics_report import build_product_analytics_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a prompt-free aggregate Aug9 activation report."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Reporting window in days (default: 7).",
    )
    args = parser.parse_args()

    initialise_database()
    report = build_product_analytics_report(days=args.days)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
