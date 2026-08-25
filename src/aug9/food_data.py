import json
from pathlib import Path


def load_food_data():

    food_file = Path(
        "data/singapore_food.json"
    )

    return json.loads(
        food_file.read_text()
    )


def load_hawker_data():
    hawker_file = Path("data/singapore_hawkers.json")
    return json.loads(hawker_file.read_text())
