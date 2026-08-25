from aug9.core.database import initialise_database
from aug9.discovery.eventbrite_events import EventbriteEventImporter


def main() -> None:
    initialise_database()
    summary = EventbriteEventImporter.from_environment().run()
    print(
        "Eventbrite event import complete: "
        f"received={summary.received}, "
        f"upserted={summary.upserted}, "
        f"rejected={summary.rejected}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
