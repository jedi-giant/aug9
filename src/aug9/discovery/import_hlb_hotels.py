from aug9.core.database import initialise_database
from aug9.discovery.hlb_hotels import HlbHotelImporter
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    initialise_database()
    summary = HlbHotelImporter(DiscoveryRepository()).run()
    print(
        "HLB hotel import complete: "
        f"received={summary.received}, "
        f"upserted={summary.upserted}, "
        f"rejected={summary.rejected}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
