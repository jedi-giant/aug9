import argparse
from pathlib import Path

from aug9.core.database import initialise_database
from aug9.discovery.playgrounds import PlaygroundGeoJsonImporter
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Singapore playground GeoJSON")
    default_path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "singapore_playgrounds_with_age_fit.geojson"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=default_path,
        help="Path to a GeoJSON FeatureCollection (defaults to the bundled dataset)",
    )
    args = parser.parse_args()
    initialise_database()
    summary = PlaygroundGeoJsonImporter(DiscoveryRepository()).run(args.path)
    print(
        "Playground import complete: "
        f"received={summary.received}, upserted={summary.upserted}, "
        f"rejected={summary.rejected}, run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
