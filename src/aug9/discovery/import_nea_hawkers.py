from aug9.core.database import initialise_database
from aug9.discovery.nea_hawkers import NeaHawkerImporter
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    initialise_database()
    summary = NeaHawkerImporter(DiscoveryRepository()).run()
    print(
        "NEA hawker import complete: "
        f"received={summary.received}, "
        f"upserted={summary.upserted}, "
        f"rejected={summary.rejected}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
