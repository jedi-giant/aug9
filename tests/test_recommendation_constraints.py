from aug9.core.recommendation import (
    ConfidenceLabel,
    RecommendationCandidate,
    RecommendationConstraints,
    RecommendationEngine,
    extract_recommendation_constraints,
)


def test_extracts_explicit_food_constraints_without_inference():
    constraints = extract_recommendation_constraints(
        "Find halal lunch near me under $15 that is open now"
    )

    assert constraints.budget_sgd == 15
    assert constraints.meal_type == "lunch"
    assert constraints.dietary_preferences == ["halal"]
    assert constraints.open_now is True


def test_leaves_unstated_food_constraints_empty():
    constraints = extract_recommendation_constraints("Find food near me")

    assert constraints.budget_sgd is None
    assert constraints.meal_type is None
    assert constraints.dietary_preferences == []
    assert constraints.open_now is False


def test_engine_applies_hard_constraints_and_separates_unknown_evidence():
    candidates = [
        RecommendationCandidate(
            id="verified",
            title="Verified nearby option",
            distance_km=0.8,
            price_max=12,
            attributes=["halal"],
            attributes_verified=True,
            open_now=True,
            relevance_score=0.9,
            provenance_score=0.9,
            freshness_score=0.85,
        ),
        RecommendationCandidate(
            id="expensive",
            title="Expensive option",
            distance_km=0.2,
            price_max=25,
            attributes=["halal"],
            attributes_verified=True,
            open_now=True,
        ),
        RecommendationCandidate(
            id="unknown",
            title="Unknown evidence option",
            distance_km=0.1,
        ),
    ]

    outcome = RecommendationEngine().rank(
        candidates,
        RecommendationConstraints(
            budget_sgd=15,
            dietary_preferences=["halal"],
            open_now=True,
        ),
    )

    assert [item.candidate.id for item in outcome.ranked] == ["verified"]
    assert outcome.ranked[0].confidence is ConfidenceLabel.HIGH
    assert [item.reasons for item in outcome.excluded] == [["over_budget"]]
    assert outcome.insufficient_evidence[0].reasons == [
        "price_unknown",
        "opening_status_unknown",
        "attributes_unverified",
    ]


def test_engine_ranking_is_explainable_and_deterministic():
    candidates = [
        RecommendationCandidate(
            id="far",
            title="Far option",
            distance_km=5,
            relevance_score=0.8,
            provenance_score=0.8,
            freshness_score=0.8,
        ),
        RecommendationCandidate(
            id="near",
            title="Near option",
            distance_km=0.5,
            relevance_score=0.8,
            provenance_score=0.8,
            freshness_score=0.8,
        ),
    ]

    outcome = RecommendationEngine().rank(candidates, RecommendationConstraints())

    assert [item.candidate.id for item in outcome.ranked] == ["near", "far"]
    assert outcome.ranked[0].total_score > outcome.ranked[1].total_score
    assert {factor.name for factor in outcome.ranked[0].factors} == {
        "distance",
        "relevance",
        "provenance",
        "freshness",
    }
    assert any("km away" in factor.explanation for factor in outcome.ranked[0].factors)


def test_engine_rejects_unbounded_result_limits():
    try:
        RecommendationEngine().rank([], RecommendationConstraints(), limit=51)
    except ValueError as error:
        assert "between 1 and 50" in str(error)
    else:
        raise AssertionError("Expected an invalid limit to fail")
