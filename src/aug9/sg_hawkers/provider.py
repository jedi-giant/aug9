from typing import Protocol

from aug9.core.models import Place
from aug9.food_data import load_hawker_data


class HawkerProvider(Protocol):
    def discover(self, query: str | None = None) -> list[Place]: ...


class CuratedHawkerProvider:
    """Discover hawker centres represented in Aug9's curated location catalog."""

    def discover(self, query: str | None = None) -> list[Place]:
        results = [Place(**item) for item in load_hawker_data()]
        if not query:
            return results

        normalized = query.casefold().strip()
        matches = [place for place in results if normalized in place.name.casefold()]
        return matches or results
