import httpx

from aug9.core.database import initialise_database
from aug9.discovery.public_events import USER_AGENT, run_public_event_imports
from aug9.discovery.repository import DiscoveryRepository


def main() -> None:
    initialise_database()
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        results = run_public_event_imports(
            DiscoveryRepository(),
            client,
            on_source_start=lambda source_id: print(
                f"{source_id}: starting", flush=True
            ),
            on_source_progress=lambda source_id, received, upserted, rejected: print(
                f"{source_id}: progress received={received}, "
                f"upserted={upserted}, rejected={rejected}",
                flush=True,
            ),
        )
    for source_id, summary in results:
        if isinstance(summary, Exception):
            print(
                f"{source_id}: failed={type(summary).__name__}: "
                f"{str(summary)[:200]}"
            )
            continue
        print(
            f"{source_id}: received={summary.received}, "
            f"upserted={summary.upserted}, rejected={summary.rejected}, "
            f"run_id={summary.run_id}"
        )
        for reason, count in summary.rejection_reasons.items():
            print(f"{source_id}: rejected_reason count={count} reason={reason}")


if __name__ == "__main__":
    main()
