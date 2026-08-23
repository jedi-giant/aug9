from aug9.food import get_food_recommendations
from aug9.models import SearchStatus


def test_food_recommendations_for_maxwell():

    result = get_food_recommendations(
        "Maxwell Food Centre"
    )

    assert result.status == SearchStatus.SUCCESS
    assert len(result.recommendations) > 0
    assert (
        result.recommendations[0].location
        == "Maxwell Food Centre"
    )
