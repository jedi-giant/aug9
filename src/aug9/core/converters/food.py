from aug9.core.models import Place
from aug9.models import FoodRecommendation


def food_to_recommendation(item: dict) -> FoodRecommendation:
    return FoodRecommendation(
        name=item["name"],
        description=item["description"],
        place=Place(
            name=item["location"],
            place_type="hawker_centre",
        ),
    )
