import argparse
import os

from aug9.core.database import initialise_database
from aug9.discovery.google_food_ratings import (
    GoogleFoodPlaceLinker,
    GooglePlacesClient,
)
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link active SFA food establishments to Google Place IDs"
    )
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    initialise_database()
    places = GooglePlacesClient(os.getenv("GOOGLE_PLACES_API_KEY", ""))
    summary = GoogleFoodPlaceLinker(DiscoveryRepository(), places).run(
        limit=args.limit
    )
    print(
        "Google food place linking complete: "
        f"received={summary.received}, linked={summary.linked}, "
        f"rejected={summary.rejected}"
    )


if __name__ == "__main__":
    main()
