import os

PLANNER_MODE = os.getenv(
    "PLANNER_MODE",
    "rule",
)


def composite_journeys_enabled() -> bool:
    return os.getenv("COMPOSITE_JOURNEYS_ENABLED", "true").casefold() not in {
        "0",
        "false",
        "no",
        "off",
    }
