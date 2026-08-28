import re
from enum import StrEnum
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
    party_size: int | None = Field(default=None, ge=1, le=100)
    max_distance_km: float | None = Field(default=None, gt=0, le=100)
    required_attributes: list[str] = Field(default_factory=list)

    @classmethod
    def from_entities(cls, entities: dict[str, Any]) -> "RecommendationConstraints":
        return cls(
            budget_sgd=entities.get("budget_sgd"),
            meal_type=entities.get("meal_type"),
            dietary_preferences=entities.get("dietary_preferences") or [],
            open_now=bool(entities.get("open_now", False)),
            party_size=entities.get("party_size"),
            max_distance_km=entities.get("max_distance_km"),
            required_attributes=entities.get("required_attributes") or [],
        )


class ConfidenceLabel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationCandidate(BaseModel):
    id: str
    title: str
    distance_km: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    attributes: list[str] = Field(default_factory=list)
    attributes_verified: bool = False
    open_now: bool | None = None
    max_party_size: int | None = Field(default=None, ge=1)
    relevance_score: float = Field(default=0.5, ge=0, le=1)
    provenance_score: float = Field(default=0, ge=0, le=1)
    freshness_score: float = Field(default=0, ge=0, le=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class RankingFactor(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    weight: float = Field(gt=0, le=1)
    explanation: str


class RankedRecommendation(BaseModel):
    candidate: RecommendationCandidate
    total_score: float = Field(ge=0, le=1)
    confidence: ConfidenceLabel
    factors: list[RankingFactor]


class IneligibleRecommendation(BaseModel):
    candidate: RecommendationCandidate
    reasons: list[str]


class RecommendationOutcome(BaseModel):
    ranked: list[RankedRecommendation] = Field(default_factory=list)
    excluded: list[IneligibleRecommendation] = Field(default_factory=list)
    insufficient_evidence: list[IneligibleRecommendation] = Field(default_factory=list)


class RecommendationEngine:
    WEIGHTS = {
        "distance": 0.35,
        "relevance": 0.30,
        "provenance": 0.20,
        "freshness": 0.15,
    }

    def rank(
        self,
        candidates: list[RecommendationCandidate],
        constraints: RecommendationConstraints,
        *,
        limit: int = 5,
    ) -> RecommendationOutcome:
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")

        eligible: list[RecommendationCandidate] = []
        excluded: list[IneligibleRecommendation] = []
        insufficient: list[IneligibleRecommendation] = []
        required_attributes = {
            *[item.casefold() for item in constraints.dietary_preferences],
            *[item.casefold() for item in constraints.required_attributes],
        }

        for candidate in candidates:
            failed, unknown = self._eligibility_reasons(
                candidate,
                constraints,
                required_attributes,
            )
            if failed:
                excluded.append(
                    IneligibleRecommendation(candidate=candidate, reasons=failed)
                )
            elif unknown:
                insufficient.append(
                    IneligibleRecommendation(candidate=candidate, reasons=unknown)
                )
            else:
                eligible.append(candidate)

        ranked = sorted(
            (self._score(candidate) for candidate in eligible),
            key=lambda item: (-item.total_score, item.candidate.title.casefold()),
        )[:limit]
        return RecommendationOutcome(
            ranked=ranked,
            excluded=excluded,
            insufficient_evidence=insufficient,
        )

    @staticmethod
    def _eligibility_reasons(candidate, constraints, required_attributes):
        failed: list[str] = []
        unknown: list[str] = []
        if constraints.budget_sgd is not None:
            if candidate.price_max is None:
                unknown.append("price_unknown")
            elif candidate.price_max > constraints.budget_sgd:
                failed.append("over_budget")
        if constraints.open_now:
            if candidate.open_now is None:
                unknown.append("opening_status_unknown")
            elif not candidate.open_now:
                failed.append("closed_now")
        if required_attributes:
            if not candidate.attributes_verified:
                unknown.append("attributes_unverified")
            elif not required_attributes.issubset(
                {item.casefold() for item in candidate.attributes}
            ):
                failed.append("required_attributes_missing")
        if constraints.max_distance_km is not None:
            if candidate.distance_km is None:
                unknown.append("distance_unknown")
            elif candidate.distance_km > constraints.max_distance_km:
                failed.append("too_far")
        if constraints.party_size is not None:
            if candidate.max_party_size is None:
                unknown.append("party_capacity_unknown")
            elif candidate.max_party_size < constraints.party_size:
                failed.append("party_too_large")
        return failed, unknown

    def _score(self, candidate: RecommendationCandidate) -> RankedRecommendation:
        values = {
            "relevance": candidate.relevance_score,
            "provenance": candidate.provenance_score,
            "freshness": candidate.freshness_score,
        }
        if candidate.distance_km is not None:
            values["distance"] = max(0.0, 1.0 - min(candidate.distance_km, 10) / 10)
        total_weight = sum(self.WEIGHTS[name] for name in values)
        factors = [
            RankingFactor(
                name=name,
                score=round(score, 4),
                weight=round(self.WEIGHTS[name] / total_weight, 4),
                explanation=self._explanation(name, candidate, score),
            )
            for name, score in values.items()
        ]
        total_score = sum(item.score * item.weight for item in factors)
        confidence = (
            ConfidenceLabel.HIGH
            if candidate.provenance_score >= 0.8 and candidate.freshness_score >= 0.8
            else ConfidenceLabel.MEDIUM
            if candidate.provenance_score >= 0.5 and candidate.freshness_score >= 0.5
            else ConfidenceLabel.LOW
        )
        return RankedRecommendation(
            candidate=candidate,
            total_score=round(total_score, 4),
            confidence=confidence,
            factors=factors,
        )

    @staticmethod
    def _explanation(name, candidate, score):
        if name == "distance":
            return f"Approximately {candidate.distance_km:.1f} km away"
        if name == "relevance":
            return "Relevance to the requested intent and preferences"
        if name == "provenance":
            return "Confidence in the supporting source evidence"
        return "Freshness of the supporting evidence"


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
