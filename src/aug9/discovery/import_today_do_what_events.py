from aug9.core.database import initialise_database
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.today_do_what_events import TodayDoWhatEventImporter


def main() -> None:
    initialise_database()
    summary = TodayDoWhatEventImporter.from_environment(DiscoveryRepository()).run()
    print(
        "Today Do What event import complete: "
        f"received={summary.received}, "
        f"upserted={summary.upserted}, "
        f"rejected={summary.rejected}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
