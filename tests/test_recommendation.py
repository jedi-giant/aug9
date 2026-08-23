from aug9.core.models import Place
from aug9.core.recommendation import Recommendation


def test_recommendation():

    recommendation = Recommendation(
        title="Lunch at Maxwell Food Centre",
        reason="Popular local food options nearby",
        places=[
            Place(
                name="Maxwell Food Centre",
                place_type="hawker_centre",
            )
        ],
        actions=[
            "Try chicken rice"
        ],
    )

    assert recommendation.title == "Lunch at Maxwell Food Centre"
    assert recommendation.places[0].name == "Maxwell Food Centre"
