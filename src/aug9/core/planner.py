import re

from pydantic import BaseModel, Field

class Plan(BaseModel):
    intent: str
    required_capabilities: list[str]
    entities: dict[str, str | None] = Field(
        default_factory=dict
    )

def extract_entities(
    user_input: str,
) -> dict[str, str]:

    entities = {}

    known_locations = [
        "Maxwell Food Centre",
        "Marina Bay Sands",
        "Tanjong Pagar",
    ]

    for location in known_locations:
        if location.lower() in user_input.lower():
            entities["location"] = location

    lowered = user_input.lower()
    matched_locations = [
        location
        for location in known_locations
        if location.lower() in lowered
    ]
    if "from" in lowered and "to" in lowered and len(matched_locations) >= 2:
        entities["origin"] = matched_locations[0]
        entities["destination"] = matched_locations[1]

    return entities

def create_plan(
    user_input: str,
) -> Plan:

    text = user_input.lower()

    capabilities = []
    lifeops_request = any(
        phrase in text
        for phrase in [
            "plan my day", "plan my saturday", "plan my sunday",
            "plan my weekend", "plan a day", "day itinerary",
            "weekend itinerary",
        ]
    )
    if lifeops_request:
        capabilities.extend(["events", "food", "weather", "transport", "lifeops"])
    padded_text = f" {text} "
    if any(
        marker in padded_text
        for marker in [
            " near ",
            " at ",
            " from ",
            " to ",
            " where ",
            " around ",
        ]
    ):
        capabilities.append("place_resolution")

    if any(
        word in text
        for word in [
            "weather",
            "rain",
            "sunny",
        ]
    ):
        capabilities.append("weather")

    if any(
        word in text
        for word in [
            "walk",
            "go",
            "travel",
            "directions",
            "public transport",
            "transit",
            "mrt",
            "bus",
            "get to",
            "get from",
            "how do i get",
            "route",
        ]
    ):
        capabilities.append("transport")

    if any(word in text for word in ["cycle", "cycling", "bike"]):
        capabilities.append("transport")

    travel_mode = None
    if any(word in text for word in ["cycle", "cycling", "bike"]):
        travel_mode = "cycle"
    elif any(word in text for word in ["drive", "driving", "taxi"]):
        travel_mode = "drive"
    elif any(phrase in text for phrase in ["public transport", "transit", "mrt", "bus"]):
        travel_mode = "public_transport"
    elif "walk" in text:
        travel_mode = "walk"

    if any(
        phrase in text
        for phrase in [
            "hawker centre",
            "hawker centres",
            "hawker center",
            "hawker centers",
        ]
    ):
        capabilities.append("hawkers")

    if any(word in text for word in ["hotel", "hotels", "accommodation"]):
        capabilities.append("hotels")

    if any(
        phrase in text
        for phrase in [
            "event", "events", "activity", "activities", "what to do",
            "things to do", "weekend", "concert", "exhibition", "festival",
        ]
    ):
        capabilities.append("events")

    if any(
        phrase in text
        for phrase in [
            "passport", "singpass", "cpf", "income tax", "iras", "hdb",
            "bto", "work pass", "work permit", "government service",
            "government services", "healthhub", "identity card", "nric",
            "birth", "birth certificate", "register birth", "marriage", "get married",
            "driving licence", "driving license", "national service",
            "ns registration", "primary 1", "p1 registration",
            "start a business", "register company",
        ]
    ):
        capabilities.append("services")
        entities = extract_entities(user_input)
        entities["service_query"] = user_input
    else:
        entities = extract_entities(user_input)

    if lifeops_request:
        entities["plan_type"] = "weekend" if "weekend" in text else "day"
    if travel_mode:
        entities["travel_mode"] = travel_mode

    explicit_food_request = any(
        re.search(rf"\b{re.escape(word)}\b", text)
        for word in [
            "eat", "bite", "breakfast", "lunch", "dinner", "restaurant",
            "cafe", "café", "recommend food",
        ]
    )
    incidental_food_place_name = (
        any(name in text for name in ("food centre", "food center"))
        and any(capability != "place_resolution" for capability in capabilities)
        and not explicit_food_request
    )
    if ("food" in text or explicit_food_request) and not incidental_food_place_name:
        capabilities.append("food")

    return Plan(
        intent=user_input,
        required_capabilities=list(dict.fromkeys(capabilities)),
        entities=entities,
    )
