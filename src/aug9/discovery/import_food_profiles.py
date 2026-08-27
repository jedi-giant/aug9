import argparse
from pathlib import Path

from aug9.core.database import initialise_database
from aug9.discovery.food_profiles import FoodProfileImporter
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an authorised food profile CSV")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument(
        "--permission",
        required=True,
        choices=["open_data", "licensed_partner", "legal_reviewed"],
    )
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--license-name")
    parser.add_argument("--base-url")
    args = parser.parse_args()

    initialise_database()
    source = DiscoverySource(
        id=args.source_id,
        name=args.source_name,
        permission=SourcePermission(args.permission),
        attribution=args.attribution,
        license_name=args.license_name,
        base_url=args.base_url,
    )
    summary = FoodProfileImporter(DiscoveryRepository(), source).run(args.file)
    print(
        "Food profile import complete: "
        f"received={summary.received}, upserted={summary.upserted}, "
        f"rejected={summary.rejected}, run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
