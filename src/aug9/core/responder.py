from aug9.core.executor import ExecutionResult


def compose_response(
    execution: ExecutionResult,
) -> str:

    messages = []

    food = execution.outputs.get("food")

    if food:
        if hasattr(food, "recommendations"):
            if food.recommendations:
                names = [
                    item.name
                    for item in food.recommendations
                ]

                messages.append(
                    "You can try: "
                    + ", ".join(names)
                    + "."
                )

    hawkers = execution.outputs.get("hawkers")

    if hawkers:
        if getattr(hawkers, "success", False):
            names = [place["name"] for place in hawkers.data.get("places", [])]
            if names:
                messages.append("Hawker centres: " + ", ".join(names) + ".")
        elif getattr(hawkers, "summary", None):
            messages.append(hawkers.summary)

    hotels = execution.outputs.get("hotels")

    if hotels:
        if getattr(hotels, "success", False):
            names = [place["name"] for place in hotels.data.get("places", [])]
            if names:
                messages.append("Licensed hotels: " + ", ".join(names) + ".")
        elif getattr(hotels, "summary", None):
            messages.append(hotels.summary)

    weather = execution.outputs.get("weather")

    if weather:
        if getattr(weather, "success", False):
            forecast = weather.data.get("weather", {}).get("forecast")
            if forecast:
                messages.append(
                    f"Weather forecast: {forecast}."
                )
        if hasattr(weather, "weather"):
            if weather.weather:
                messages.append(
                    f"Weather forecast: "
                    f"{weather.weather.forecast}."
                )

    transport = execution.outputs.get("transport")

    if transport:
        if getattr(transport, "success", False):
            route = transport.data.get("route", {})
            summary = route.get("summary") or transport.summary
            if summary:
                messages.append(summary)
        elif getattr(transport, "summary", None):
            messages.append(transport.summary)

    return " ".join(messages)
