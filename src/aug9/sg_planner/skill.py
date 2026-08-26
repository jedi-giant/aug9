import math
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult


SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")
WALKABLE_LEG_METERS = 1500.0


class SgPlannerSkill(Aug9Skill):
    """Marks a request for orchestration across existing Singapore skills."""

    name = "sg_planner"
    description = "Coordinate Singapore weather, food, and activity planning"
    version = "0.1.0"

    @property
    def capabilities(self) -> list[str]:
        return ["lifeops"]

    def execute(self, context: UserContext, entities: dict[str, Any]) -> SkillResult:
        has_location = bool(context.current_place or entities.get("location"))
        outputs = entities.get("_lifeops_outputs", {})
        itinerary = self._build_itinerary(context, outputs)
        itinerary = self._order_event_stops(itinerary)
        self._assign_times(itinerary, context.intent)
        itinerary = self._order_by_schedule(itinerary)
        travel_legs, actions = self._build_travel_legs(itinerary)
        return SkillResult(
            success=True,
            data={
                "plan_type": entities.get("plan_type", "day"),
                "location_available": has_location,
                "itinerary": itinerary,
                "travel_legs": travel_legs,
                "weather": self._skill_data(outputs, "weather").get("weather"),
                "transport": self._skill_data(outputs, "transport").get("route"),
            },
            summary=(
                f"Your Singapore day plan has {len(itinerary)} planned stops."
                if itinerary
                else "Singapore day-plan coordination is active."
            ),
            actions=actions,
        )

    @classmethod
    def _build_itinerary(
        cls,
        context: UserContext,
        outputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        itinerary: list[dict[str, Any]] = []
        if context.current_place is not None:
            itinerary.append(
                {
                    "order": 1,
                    "type": "start",
                    "title": f"Start at {context.current_place.name}",
                    "location": context.current_place.name,
                    "latitude": context.current_place.latitude,
                    "longitude": context.current_place.longitude,
                }
            )

        food = outputs.get("food")
        recommendations = getattr(food, "recommendations", [])
        if recommendations:
            recommendation = recommendations[0]
            itinerary.append(
                {
                    "order": len(itinerary) + 1,
                    "type": "food",
                    "title": recommendation.name,
                    "description": recommendation.description,
                    "location": recommendation.place.name,
                    "latitude": (
                        recommendation.place.latitude
                        if recommendation.place.latitude is not None
                        else cls._matching_context_coordinate(
                            context, recommendation.place.name, "latitude"
                        )
                    ),
                    "longitude": (
                        recommendation.place.longitude
                        if recommendation.place.longitude is not None
                        else cls._matching_context_coordinate(
                            context, recommendation.place.name, "longitude"
                        )
                    ),
                }
            )

        for event in cls._skill_data(outputs, "events").get("events", []):
            itinerary.append(
                {
                    "order": len(itinerary) + 1,
                    "type": "event",
                    "title": event.get("name"),
                    "starts_at": event.get("starts_at"),
                    "ends_at": event.get("ends_at"),
                    "location": event.get("address"),
                    "booking_url": event.get("booking_url") or event.get("source_url"),
                    "latitude": event.get("latitude"),
                    "longitude": event.get("longitude"),
                }
            )
        return itinerary

    @staticmethod
    def _matching_context_coordinate(
        context: UserContext,
        place_name: str,
        coordinate: str,
    ) -> float | None:
        if (
            context.current_place is not None
            and context.current_place.name.casefold() == place_name.casefold()
        ):
            return getattr(context.current_place, coordinate)
        return None

    @classmethod
    def _order_event_stops(
        cls, itinerary: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        prefix = [item for item in itinerary if item["type"] != "event"]
        remaining = [item for item in itinerary if item["type"] == "event"]
        ordered: list[dict[str, Any]] = []
        anchor = prefix[-1] if prefix else None
        while remaining:
            candidates = [
                (cls._distance_meters(anchor, item), index, item)
                for index, item in enumerate(remaining)
            ]
            _, index, selected = min(
                candidates,
                key=lambda candidate: (
                    candidate[0] is None,
                    candidate[0] or 0,
                    candidate[1],
                ),
            )
            ordered.append(selected)
            anchor = selected
            remaining.pop(index)
        result = [*prefix, *ordered]
        for index, item in enumerate(result, start=1):
            item["order"] = index
        return result

    @staticmethod
    def _assign_times(
        itinerary: list[dict[str, Any]], intent: str | None
    ) -> None:
        target = SgPlannerSkill._target_date(intent)
        event_hour = 14
        for item in itinerary:
            if item["type"] == "start":
                hour = 10
            elif item["type"] == "food":
                hour = 12
            else:
                hour = event_hour
                event_hour += 3
                starts_at = SgPlannerSkill._parse_datetime(item.get("starts_at"))
                if (
                    starts_at is not None
                    and starts_at.astimezone(SINGAPORE_TIMEZONE).date() == target.date()
                    and (starts_at.hour or starts_at.minute)
                ):
                    item["scheduled_for"] = starts_at.astimezone(
                        SINGAPORE_TIMEZONE
                    ).isoformat()
                    continue
            item["scheduled_for"] = target.replace(hour=hour).isoformat()

    @staticmethod
    def _target_date(intent: str | None) -> datetime:
        now = datetime.now(SINGAPORE_TIMEZONE)
        text = (intent or "").casefold()
        if "tomorrow" in text:
            target = now + timedelta(days=1)
        elif "saturday" in text or "weekend" in text:
            target = now + timedelta(days=(5 - now.weekday()) % 7)
        elif "sunday" in text:
            target = now + timedelta(days=(6 - now.weekday()) % 7)
        else:
            target = now
        return target.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SINGAPORE_TIMEZONE)
        return parsed

    @staticmethod
    def _order_by_schedule(
        itinerary: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        result = sorted(
            itinerary,
            key=lambda item: item.get("scheduled_for") or "",
        )
        for index, item in enumerate(result, start=1):
            item["order"] = index
        return result

    @classmethod
    def _build_travel_legs(
        cls, itinerary: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[SkillAction]]:
        legs: list[dict[str, Any]] = []
        actions: list[SkillAction] = []
        for origin, destination in zip(itinerary, itinerary[1:]):
            if not origin.get("location") or not destination.get("location"):
                continue
            if origin["location"].casefold() == destination["location"].casefold():
                continue
            distance = cls._distance_meters(origin, destination)
            mode = (
                "walk"
                if distance is not None and distance <= WALKABLE_LEG_METERS
                else "public_transport"
            )
            google_mode = "walking" if mode == "walk" else "transit"
            legs.append(
                {
                    "order": len(legs) + 1,
                    "from": origin["location"],
                    "to": destination["location"],
                    "distance_meters": round(distance) if distance is not None else None,
                    "recommended_mode": mode,
                }
            )
            url = cls._directions_url(
                origin["location"], destination["location"], google_mode
            )
            actions.append(
                SkillAction(
                    type="open_url",
                    label=f"Directions to {destination['title']}",
                    url=url,
                    metadata={
                        "capability": "lifeops",
                        "travel_mode": mode,
                        "leg": len(legs),
                    },
                )
            )
        return legs, actions

    @staticmethod
    def _directions_url(origin: str, destination: str, mode: str) -> str:
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={quote_plus(origin)}"
            f"&destination={quote_plus(destination)}"
            f"&travelmode={mode}"
        )

    @staticmethod
    def _distance_meters(
        origin: dict[str, Any] | None, destination: dict[str, Any]
    ) -> float | None:
        if origin is None:
            return None
        values = (
            origin.get("latitude"),
            origin.get("longitude"),
            destination.get("latitude"),
            destination.get("longitude"),
        )
        if any(value is None for value in values):
            return None
        lat1, lon1, lat2, lon2 = (float(value) for value in values)
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        haversine = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return 6_371_000 * 2 * math.atan2(
            math.sqrt(haversine), math.sqrt(1 - haversine)
        )

    @staticmethod
    def _skill_data(outputs: dict[str, Any], capability: str) -> dict[str, Any]:
        output = outputs.get(capability)
        data = getattr(output, "data", {})
        return data if isinstance(data, dict) else {}
