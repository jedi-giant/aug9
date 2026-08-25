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

    if transport and getattr(transport, "success", False):
        route = transport.data.get("route", {})
        summary = route.get("summary") or transport.summary
        if summary:
            messages.append(summary)

    return " ".join(messages)
