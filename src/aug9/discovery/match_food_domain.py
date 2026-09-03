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
    parser.add_argument(
        "--source-id",
        action="append",
        help="Only match this imported source ID; repeat for multiple sources",
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=0,
        help="Return up to this many decisions per outcome instead of all decisions",
    )
    args = parser.parse_args()
    initialise_database()
    matcher = (
        FoodEntityMatcher(source_ids=tuple(args.source_id))
        if args.source_id
        else FoodEntityMatcher()
    )
    report = matcher.run(apply=args.apply, limit=args.limit)
    if args.summary_only:
        report.pop("decisions", None)
    elif args.sample_limit:
        if args.sample_limit < 1 or args.sample_limit > 100:
            parser.error("--sample-limit must be between 1 and 100")
        decisions = report.pop("decisions")
        report["samples"] = {
            outcome: [
                item for item in decisions if item["outcome"] == outcome
            ][: args.sample_limit]
            for outcome in ("matched", "ambiguous", "unmatched")
        }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
