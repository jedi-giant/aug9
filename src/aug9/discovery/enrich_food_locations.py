from aug9.core.database import initialise_database
from aug9.discovery.food_locations import FoodLocationEnricher


def main() -> None:
    initialise_database()
    summary = FoodLocationEnricher.from_environment().run()
    print(
        "Food location enrichment complete: "
        f"received={summary.received}, upserted={summary.upserted}, "
        f"rejected={summary.rejected}, unique_queries={summary.unique_queries}, "
        f"run_id={summary.run_id}"
    )


if __name__ == "__main__":
    main()
