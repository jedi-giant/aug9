from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FoodRankingCandidate(BaseModel):
    id: str
    name: str
    distance_km: float = Field(ge=0, le=20)
    relevance_score: float = Field(ge=0, le=1)
    provenance_score: float = Field(ge=0, le=1)
    freshness_score: float = Field(ge=0, le=1)
    positive_organic_editorial_records: int = Field(default=0, ge=0, le=20)


class FoodRankingCase(BaseModel):
    id: str
    description: str
    expected_top_id: str
    candidates: list[FoodRankingCandidate] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def validate_expected_candidate(self):
        candidate_ids = [candidate.id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Evaluation candidate IDs must be unique")
        if self.expected_top_id not in candidate_ids:
            raise ValueError("expected_top_id must reference a candidate")
        return self


@dataclass(frozen=True)
class FoodRankingFactor:
    name: str
    score: float
    weight: float
    explanation: str


@dataclass(frozen=True)
class RankedFoodCandidate:
    candidate: FoodRankingCandidate
    score: float
    factors: tuple[FoodRankingFactor, ...]


class FoodRankingPolicy:
    """Offline food-ranking policy; it is not connected to live recommendations."""

    WEIGHTS = {
        "distance": 0.40,
        "relevance": 0.25,
        "editorial": 0.15,
        "provenance": 0.10,
        "freshness": 0.10,
    }

    def rank(self, candidates: list[FoodRankingCandidate]) -> list[RankedFoodCandidate]:
        ranked = [self._score(candidate) for candidate in candidates]
        return sorted(
            ranked,
            key=lambda item: (-item.score, item.candidate.name.casefold()),
        )

    def _score(self, candidate: FoodRankingCandidate) -> RankedFoodCandidate:
        values = {
            "distance": max(0.0, 1.0 - min(candidate.distance_km, 5.0) / 5.0),
            "relevance": candidate.relevance_score,
            "editorial": min(1.0, candidate.positive_organic_editorial_records / 2),
            "provenance": candidate.provenance_score,
            "freshness": candidate.freshness_score,
        }
        factors = tuple(
            FoodRankingFactor(
                name=name,
                score=round(value, 4),
                weight=weight,
                explanation=self._explanation(name, candidate),
            )
            for name, weight in self.WEIGHTS.items()
            for value in (values[name],)
        )
        score = round(sum(item.score * item.weight for item in factors), 4)
        return RankedFoodCandidate(candidate, score, factors)

    @staticmethod
    def _explanation(name: str, candidate: FoodRankingCandidate) -> str:
        if name == "distance":
            return f"Approximately {candidate.distance_km:.1f} km away"
        if name == "relevance":
            return "Fit with the expressed food request"
        if name == "editorial":
            count = candidate.positive_organic_editorial_records
            return f"{count} active organic editorial food-quality record(s)"
        if name == "provenance":
            return "Confidence in the source and entity match"
        return "Freshness of the supporting evidence"


def load_food_ranking_cases(path: Path) -> list[FoodRankingCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload or len(payload) > 100:
        raise ValueError("Evaluation set must contain between 1 and 100 cases")
    cases = [FoodRankingCase.model_validate(item) for item in payload]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    return cases


def evaluate_food_ranking(path: Path) -> dict[str, Any]:
    policy = FoodRankingPolicy()
    results = []
    for case in load_food_ranking_cases(path):
        ranked = policy.rank(case.candidates)
        top = ranked[0]
        runner_up = ranked[1]
        results.append(
            {
                "id": case.id,
                "description": case.description,
                "expected_top_id": case.expected_top_id,
                "actual_top_id": top.candidate.id,
                "passed": top.candidate.id == case.expected_top_id,
                "top_score": top.score,
                "runner_up_score": runner_up.score,
                "margin": round(top.score - runner_up.score, 4),
                "top_factors": [factor.__dict__ for factor in top.factors],
            }
        )
    passed = sum(1 for result in results if result["passed"])
    return {
        "mode": "offline",
        "live_ranking_affected": False,
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4),
        "cases": results,
    }
