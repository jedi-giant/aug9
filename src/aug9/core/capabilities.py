from aug9.core.skills import (
    execute_food,
    execute_weather,
)


CAPABILITIES = {
    "food": {
        "description":
            "Recommend Singapore food places based on location",
        "parameters": [
            "location",
        ],
        "handler": execute_food,
    },

    "weather": {
        "description":
            "Provide weather forecast for a location",
        "parameters": [
            "location",
        ],
        "handler": execute_weather,
    },
}
