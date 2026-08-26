import json

from aug9.core.database import initialise_database
from aug9.discovery.event_catalog_report import build_event_catalog_report


def main() -> None:
    initialise_database()
    report = build_event_catalog_report()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
