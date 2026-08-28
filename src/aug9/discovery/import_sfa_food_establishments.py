from aug9.core.database import initialise_database
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SfaFoodEstablishmentImporter


def main() -> None:
    initialise_database()
    summary = SfaFoodEstablishmentImporter(DiscoveryRepository()).run()
    print(
        "SFA food establishment import complete: "
        f"received={summary.received}, upserted={summary.upserted}, "
        f"rejected={summary.rejected}, run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
