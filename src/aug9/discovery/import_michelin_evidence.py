import argparse
from pathlib import Path

from aug9.core.database import initialise_database
from aug9.discovery.michelin_evidence import MichelinEvidenceImporter
from aug9.discovery.repository import DiscoveryRepository


DEFAULT_PILOT_PATH = Path("data/michelin_singapore_bib_gourmand_pilot_2026.csv")
DEFAULT_APPROVALS_PATH = Path(
    "data/michelin_singapore_bib_gourmand_approved_matches_2026.csv"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import reviewed Michelin Bib Gourmand evidence"
    )
    parser.add_argument("--pilot-file", type=Path, default=DEFAULT_PILOT_PATH)
    parser.add_argument(
        "--approvals-file", type=Path, default=DEFAULT_APPROVALS_PATH
    )
    args = parser.parse_args()
    initialise_database()
    summary = MichelinEvidenceImporter(DiscoveryRepository()).run(
        pilot_path=args.pilot_file,
        approvals_path=args.approvals_file,
    )
    print(
        "Michelin evidence import complete: "
        f"received={summary.received}, upserted={summary.upserted}, "
        f"rejected={summary.rejected}, run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
