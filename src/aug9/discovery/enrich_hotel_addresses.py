from aug9.core.database import initialise_database
from aug9.discovery.hotel_addresses import HotelAddressEnricher


def main() -> None:
    initialise_database()
    summary = HotelAddressEnricher.from_environment().run()
    print(
        "Hotel address enrichment complete: "
        f"received={summary.received}, "
        f"upserted={summary.upserted}, "
        f"rejected={summary.rejected}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
