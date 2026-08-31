from aug9.core.executor import ExecutionResult


def compose_response(
    execution: ExecutionResult,
) -> str:

    messages = []

    place = execution.outputs.get("place_resolution")
    if (
        place
        and not getattr(place, "success", True)
        and getattr(place, "summary", None)
    ):
        messages.append(place.summary)

    food = execution.outputs.get("food")

    if food:
        if getattr(food, "summary", None):
            messages.append(food.summary)
        elif hasattr(food, "recommendations"):
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
            if getattr(hawkers, "summary", None):
                messages.append(hawkers.summary)
            else:
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

    events = execution.outputs.get("events")

    if events:
        if getattr(events, "success", False):
            names = [item["name"] for item in events.data.get("events", [])]
            if names:
                messages.append("Upcoming events: " + ", ".join(names) + ".")
        elif getattr(events, "summary", None):
            messages.append(events.summary)

    playgrounds = execution.outputs.get("playgrounds")

    if playgrounds and getattr(playgrounds, "summary", None):
        messages.append(playgrounds.summary)

    services = execution.outputs.get("services")

    if services and getattr(services, "summary", None):
        messages.append(services.summary)

    weather = execution.outputs.get("weather")

    if weather:
        if getattr(weather, "success", False):
            summary = getattr(weather, "summary", None)
            forecast = weather.data.get("weather", {}).get("forecast")
            if summary:
                messages.append(summary)
            elif forecast:
                messages.append(f"Weather forecast: {forecast}.")
        if hasattr(weather, "weather"):
            if weather.weather:
                messages.append(
                    f"Weather forecast: "
                    f"{weather.weather.forecast}."
                )
        if (
            not getattr(weather, "success", True)
            and getattr(weather, "summary", None)
        ):
            messages.append(weather.summary)

    transport = execution.outputs.get("transport")

    if transport:
        if getattr(transport, "success", False):
            route = transport.data.get("route", {})
            summary = route.get("summary") or transport.summary
            if summary:
                messages.append(summary)
        elif getattr(transport, "summary", None):
            messages.append(transport.summary)

    lifeops = execution.outputs.get("lifeops")
    if lifeops and getattr(lifeops, "success", False):
        location_available = lifeops.data.get("location_available", False)
        itinerary = lifeops.data.get("itinerary", [])
        if itinerary and location_available:
            plan_messages = []
            for stop in itinerary:
                if stop.get("type") == "start":
                    plan_messages.append(stop.get("title"))
                elif stop.get("type") == "food":
                    plan_messages.append(f"Food stop: {stop.get('title')}")
                elif stop.get("title"):
                    plan_messages.append(f"Then: {stop.get('title')}")

            weather_summary = getattr(weather, "summary", None) if weather else None
            if weather and not weather_summary:
                forecast = getattr(weather, "data", {}).get("weather", {}).get(
                    "forecast"
                )
                if forecast:
                    weather_summary = f"Weather forecast: {forecast}."
            transport_summary = None
            if transport:
                transport_summary = (
                    getattr(transport, "data", {})
                    .get("route", {})
                    .get("summary")
                    or getattr(transport, "summary", None)
                )
            plan_messages.extend(
                item
                for item in (weather_summary, transport_summary)
                if item
            )
            return "Your Singapore day plan: " + ". ".join(
                item.rstrip(".") for item in plan_messages if item
            ) + "."

    response = " ".join(messages)
    if lifeops and getattr(lifeops, "success", False):
        location_available = lifeops.data.get("location_available", False)
        if response:
            response = "Your Singapore day plan: " + response
        else:
            response = "I can build your Singapore day plan."
        if not location_available:
            response += " Tell me your starting neighbourhood for local food and weather."
    return response
