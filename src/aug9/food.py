from aug9.core.models import Place
from aug9.food_data import load_food_data
from aug9.models import (
    FoodRecommendation,
    FoodResult,
    SearchStatus,
)


RAW_FOOD_DATA = load_food_data()


def get_food_recommendations(
    location: str,
) -> FoodResult:

    recommendations = []

    for item in RAW_FOOD_DATA:

        if item["place"]["name"] == location:

            recommendations.append(
                FoodRecommendation(
                    name=item["name"],
                    description=item["description"],
                    place=Place(
                        **item["place"]
                    ),
                )
            )

    return FoodResult(
        status=SearchStatus.SUCCESS,
        recommendations=recommendations,
    )
