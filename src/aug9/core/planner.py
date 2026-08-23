from pydantic import BaseModel


class Plan(BaseModel):
    intent: str
    required_capabilities: list[str]

def create_plan(
    user_input: str,
) -> Plan:

    text = user_input.lower()

    capabilities = []

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
            "route",
        ]
    ):
        capabilities.append("transport")

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
    )
