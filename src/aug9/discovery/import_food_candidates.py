import argparse
from pathlib import Path

from aug9.core.database import initialise_database
from aug9.discovery.food_candidates import (
    FoodCandidateImporter,
    FoodCandidateRepository,
)
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage an unverified food GeoJSON")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument(
        "--permission",
        default="research_only",
        choices=["research_only", "legal_reviewed"],
    )
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--base-url")
    args = parser.parse_args()

    initialise_database()
    source = DiscoverySource(
        id=args.source_id,
        name=args.source_name,
        permission=SourcePermission(args.permission),
        attribution=args.attribution,
        base_url=args.base_url,
    )
    summary = FoodCandidateImporter(
        DiscoveryRepository(),
        FoodCandidateRepository(),
        source,
    ).run(args.file)
    print(
        "Food candidate staging complete: "
        f"received={summary.received}, staged={summary.staged}, "
        f"quarantined={summary.quarantined}, rejected={summary.rejected}, "
        f"duplicates={summary.duplicates}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
