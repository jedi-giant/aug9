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
    if any(
        word in text
        for word in [
            "near",
            "at",
            "from",
            "to",
            "where",
            "around",
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
            "get to",
            "get from",
            "how do i get",
            "route",
        ]
    ):
        capabilities.append("transport")

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

    if any(
        word in text
        for word in [
            "eat",
            "food",
            "lunch",
            "dinner",
        ]
    ):
        capabilities.append("food")

    return Plan(
        intent=user_input,
        required_capabilities=capabilities,
        entities=entities,
    )
