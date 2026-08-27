from aug9.core.recommendation import extract_recommendation_constraints


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
