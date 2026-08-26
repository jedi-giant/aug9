from aug9.discovery.archive_expired_events import main as archive_expired_events
from aug9.discovery.import_public_events import main as import_public_events
from aug9.discovery.enrich_event_venues import main as enrich_event_venues


def main() -> None:
    print("Daily event refresh starting", flush=True)
    import_public_events()
    try:
        enrich_event_venues()
    except Exception as exc:
        print(f"Event venue enrichment failed: {type(exc).__name__}", flush=True)
    archive_expired_events()
    print("Daily event refresh complete", flush=True)


if __name__ == "__main__":
    main()
