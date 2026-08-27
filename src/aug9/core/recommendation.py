import re
from typing import Any

from pydantic import BaseModel, Field

from aug9.core.models import Place


class Recommendation(BaseModel):
    title: str
    reason: str
    places: list[Place] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class RecommendationConstraints(BaseModel):
    budget_sgd: float | None = Field(default=None, gt=0, le=1000)
    meal_type: str | None = None
    dietary_preferences: list[str] = Field(default_factory=list)
    open_now: bool = False

    @classmethod
    def from_entities(cls, entities: dict[str, Any]) -> "RecommendationConstraints":
        return cls(
            budget_sgd=entities.get("budget_sgd"),
            meal_type=entities.get("meal_type"),
            dietary_preferences=entities.get("dietary_preferences") or [],
            open_now=bool(entities.get("open_now", False)),
        )


def extract_recommendation_constraints(text: str) -> RecommendationConstraints:
    lowered = text.casefold()
    budget_match = re.search(
        r"(?:under|below|up to|max(?:imum)?|budget(?: of)?)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
        lowered,
    )
    meal_type = next(
        (meal for meal in ("breakfast", "lunch", "dinner", "supper") if meal in lowered),
        None,
    )
    dietary_preferences = [
        preference
        for preference in ("halal", "vegetarian", "vegan")
        if re.search(rf"\b{preference}\b", lowered)
    ]
    return RecommendationConstraints(
        budget_sgd=float(budget_match.group(1)) if budget_match else None,
        meal_type=meal_type,
        dietary_preferences=dietary_preferences,
        open_now=bool(re.search(r"\bopen\s+(?:right\s+)?now\b", lowered)),
    )
