import argparse
import os
from collections.abc import Callable

from aug9.core.database import initialise_database
from aug9.discovery.food_locations import FoodLocationEnricher, FoodLocationSummary


def run_enrichment_batches(
    enricher: FoodLocationEnricher,
    *,
    max_batches: int,
    output: Callable[[str], None] = print,
) -> list[FoodLocationSummary]:
    if max_batches < 1 or max_batches > 100:
        raise ValueError("max_batches must be between 1 and 100")

    summaries = []
    for batch_number in range(1, max_batches + 1):
        summary = enricher.run()
        summaries.append(summary)
        output(
            f"Food location enrichment batch {batch_number}: "
            f"received={summary.received}, upserted={summary.upserted}, "
            f"rejected={summary.rejected}, "
            f"unique_queries={summary.unique_queries}, run_id={summary.run_id}"
        )
        if summary.received == 0:
            break
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich SFA food locations with bounded OneMap batches"
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=int(os.getenv("FOOD_LOCATION_ENRICHMENT_MAX_BATCHES", "1")),
        help="Maximum batches to process in this invocation (1-100)",
    )
    args = parser.parse_args()
    if args.max_batches < 1 or args.max_batches > 100:
        parser.error("--max-batches must be between 1 and 100")

    initialise_database()
    summaries = run_enrichment_batches(
        FoodLocationEnricher.from_environment(),
        max_batches=args.max_batches,
    )
    print(
        "Food location enrichment complete: "
        f"batches={len(summaries)}, "
        f"received={sum(item.received for item in summaries)}, "
        f"upserted={sum(item.upserted for item in summaries)}, "
        f"rejected={sum(item.rejected for item in summaries)}, "
        f"unique_queries={sum(item.unique_queries for item in summaries)}, "
        f"catalog_complete={summaries[-1].received == 0}"
    )


if __name__ == "__main__":
    main()
