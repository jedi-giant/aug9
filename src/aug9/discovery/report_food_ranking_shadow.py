import argparse
import json

from aug9.core.database import initialise_database
from aug9.discovery.food_ranking_shadow import build_food_ranking_shadow_report
from aug9.sg_food.provider import DatabaseFoodProvider


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare current and proposed food ranking on real candidates"
    )
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--pool-limit", type=int, default=250)
    parser.add_argument("--max-distance-km", type=float, default=3.0)
    parser.add_argument(
        "--venue-kind",
        choices=("restaurant", "hawker_stall", "food_court_stall"),
    )
    args = parser.parse_args()
    initialise_database()
    provider = DatabaseFoodProvider(
        limit=args.limit,
        max_distance_km=args.max_distance_km,
    )
    report = build_food_ranking_shadow_report(
        provider,
        latitude=args.latitude,
        longitude=args.longitude,
        venue_kinds=(args.venue_kind,) if args.venue_kind else (),
        pool_limit=args.pool_limit,
        display_limit=args.limit,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
