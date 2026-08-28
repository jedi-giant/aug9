import argparse
import json
from pathlib import Path

from aug9.core.database import initialise_database
from aug9.discovery.michelin_pilot import MichelinSfaMatcher, load_michelin_pilot


DEFAULT_PILOT_PATH = Path("data/michelin_singapore_bib_gourmand_pilot_2026.csv")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate review-only SFA matches for the Michelin pilot"
    )
    parser.add_argument("--file", type=Path, default=DEFAULT_PILOT_PATH)
    parser.add_argument("--radius-km", type=float, default=0.5)
    args = parser.parse_args()
    initialise_database()
    matches = MichelinSfaMatcher(radius_km=args.radius_km).match_all(
        load_michelin_pilot(args.file)
    )
    print(
        json.dumps(
            {
                "summary": {
                    status: sum(item.status == status for item in matches)
                    for status in ("high_confidence", "review", "unmatched")
                },
                "matches": [
                    {
                        "michelin_id": item.candidate.external_id,
                        "michelin_name": item.candidate.name,
                        "entity_id": item.entity_id,
                        "entity_name": item.entity_name,
                        "entity_address": item.entity_address,
                        "distance_km": item.distance_km,
                        "name_similarity": item.name_similarity,
                        "match_score": item.match_score,
                        "status": item.status,
                        "alternatives": [
                            {
                                "entity_id": alternative.entity_id,
                                "entity_name": alternative.entity_name,
                                "entity_address": alternative.entity_address,
                                "distance_km": alternative.distance_km,
                                "name_similarity": alternative.name_similarity,
                                "match_score": alternative.match_score,
                            }
                            for alternative in item.alternatives
                        ],
                    }
                    for item in matches
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
