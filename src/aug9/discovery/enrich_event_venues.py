from aug9.core.database import initialise_database
from aug9.discovery.event_venues import EventVenueEnricher


def main() -> None:
    initialise_database()
    summary = EventVenueEnricher.from_environment().run()
    print(
        "Event venue enrichment complete: "
        f"received={summary.received}, "
        f"upserted={summary.upserted}, "
        f"rejected={summary.rejected}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
