import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aug9.discovery.food_ranking_evaluation import (
    FoodRankingCandidate,
    FoodRankingPolicy,
    evaluate_food_ranking,
    load_food_ranking_cases,
)


def test_offline_evaluation_set_passes_regression_policy():
    report = evaluate_food_ranking(
        Path("data/food_ranking_evaluation_v1.json")
    )

    assert report["mode"] == "offline"
    assert report["live_ranking_affected"] is False
    assert report["case_count"] == 5
    assert report["pass_rate"] == 1.0


def test_food_policy_is_explainable_and_deterministic():
    candidates = [
        FoodRankingCandidate(
            id="plain",
            name="Plain",
            distance_km=0.5,
            relevance_score=0.8,
            provenance_score=0.8,
            freshness_score=0.8,
        ),
        FoodRankingCandidate(
            id="editorial",
            name="Editorial",
            distance_km=0.5,
            relevance_score=0.8,
            provenance_score=0.8,
            freshness_score=0.8,
            positive_organic_editorial_records=1,
        ),
    ]

    ranked = FoodRankingPolicy().rank(candidates)

    assert ranked[0].candidate.id == "editorial"
    assert [factor.name for factor in ranked[0].factors] == [
        "distance",
        "relevance",
        "editorial",
        "provenance",
        "freshness",
    ]
    assert sum(factor.weight for factor in ranked[0].factors) == 1.0


def test_evaluation_loader_rejects_invalid_expected_candidate(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "invalid",
                    "description": "Invalid case",
                    "expected_top_id": "missing",
                    "candidates": [
                        {
                            "id": "one",
                            "name": "One",
                            "distance_km": 1,
                            "relevance_score": 0.5,
                            "provenance_score": 0.5,
                            "freshness_score": 0.5
                        },
                        {
                            "id": "two",
                            "name": "Two",
                            "distance_km": 2,
                            "relevance_score": 0.5,
                            "provenance_score": 0.5,
                            "freshness_score": 0.5
                        }
                    ]
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="expected_top_id"):
        load_food_ranking_cases(path)
