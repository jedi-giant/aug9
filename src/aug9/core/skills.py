from aug9.core.context import UserContext
from aug9.food import get_food_recommendations
from aug9.weather import get_weather

def execute_food(
    context: UserContext,
    entities: dict[str, str],
):
    if hasattr(entities, "location"):
        location = entities.location
    else:
        location = entities.get("location")
    if location:
        location = (
            location
            .replace("near ", "")
            .replace("around ", "")
            .replace("at ", "")
            .strip()
        )
    if location is None:
        if context.current_place is None:
            return "No location available"

        location = context.current_place.name

    preferences = []

    if context.memory:
        preferences = (
            context.memory.preferences
            .get("food", [])
        )

    return get_food_recommendations(
        location,
        preferences,
    )

def execute_weather(
    context: UserContext,
    entities: dict[str, str],
):
    if context.current_place is None:
        return "No location available"

    return get_weather(
        context.current_place
    )
