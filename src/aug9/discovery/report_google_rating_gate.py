import argparse
import json
import os

from aug9.core.database import initialise_database
from aug9.discovery.google_food_ratings import (
    GooglePlacesClient,
    build_google_rating_gate_report,
)
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview the Google rating recommendation gate without applying it"
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    initialise_database()
    places = GooglePlacesClient(os.getenv("GOOGLE_PLACES_API_KEY", ""))
    report = build_google_rating_gate_report(
        DiscoveryRepository(), places, limit=args.limit
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
