import argparse
from pathlib import Path

from aug9.core.database import initialise_database
from aug9.discovery.food_domain import FoodDomainImporter
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an aug9.food-domain.v1 JSON file")
    parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    initialise_database()
    print(f"Validating and importing {args.file} in one bulk transaction...")
    summary = FoodDomainImporter(DiscoveryRepository()).run(args.file)
    print(
        "Food domain import complete: "
        f"received={summary.received}, upserted={summary.upserted}, "
        f"rejected={summary.rejected}, run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
