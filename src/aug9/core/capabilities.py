from aug9.core.skills import (
    execute_food,
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

}
