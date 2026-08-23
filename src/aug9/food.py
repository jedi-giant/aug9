from aug9.models import (
    FoodRecommendation,
    FoodResult,
    SearchStatus,
)


FOOD_DATABASE = {
    "Maxwell Food Centre": [
        FoodRecommendation(
            name="Tian Tian Chicken Rice",
            description="Famous Hainanese chicken rice stall.",
            location="Maxwell Food Centre",
        ),
        FoodRecommendation(
            name="Maxwell Fuzhou Oyster Cake",
            description="Traditional crispy oyster cake.",
            location="Maxwell Food Centre",
        ),
    ]
}


def get_food_recommendations(
    location: str,
) -> FoodResult:

    recommendations = FOOD_DATABASE.get(
        location,
        [],
    )

    return FoodResult(
        status=SearchStatus.SUCCESS,
        recommendations=recommendations,
    )
