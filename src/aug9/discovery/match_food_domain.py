import argparse
import json

from aug9.core.database import initialise_database
from aug9.discovery.food_entity_matching import FoodEntityMatcher


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match imported food-domain venues to canonical SFA entities"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    initialise_database()
    report = FoodEntityMatcher().run(apply=args.apply, limit=args.limit)
    if args.summary_only:
        report.pop("decisions", None)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
