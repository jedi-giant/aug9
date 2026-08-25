from aug9.core.database import initialise_database
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    initialise_database()
    archived = DiscoveryRepository().archive_expired_events()
    print(f"Event expiry complete: archived={archived}")


if __name__ == "__main__":
    main()
