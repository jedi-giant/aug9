import httpx

from aug9.core.database import initialise_database
from aug9.discovery.public_events import (
    DISABLED_EVENT_SOURCES,
    USER_AGENT,
    run_public_event_imports,
)
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    initialise_database()
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        results = run_public_event_imports(DiscoveryRepository(), client)
    for source_id, summary in results:
        if isinstance(summary, Exception):
            print(f"{source_id}: failed={type(summary).__name__}")
            continue
        print(
            f"{source_id}: received={summary.received}, "
            f"upserted={summary.upserted}, rejected={summary.rejected}, "
            f"run_id={summary.run_id}"
        )
    for source_id, reason in DISABLED_EVENT_SOURCES.items():
        print(f"{source_id}: disabled={reason}")


if __name__ == "__main__":
    main()
