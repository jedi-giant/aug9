from datetime import UTC, datetime, timedelta
from typing import Any

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_events.provider import EventProvider


EVENT_SOURCE_LINKS = (
    (
        "Browse Honeycombers events",
        "https://thehoneycombers.com/singapore/singapore-event-calendar/search-events/",
    ),
    (
        "Browse Visit Singapore events",
        "https://www.visitsingapore.com/whats-happening/all-happenings/",
    ),
)


class SgEventsSkill(Aug9Skill):
    name = "sg_events"
    description = "Discover governed Singapore activities and events"
    version = "0.1.0"

    def __init__(self, provider: EventProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["events"]

    def execute(self, context: UserContext, entities: dict[str, Any]) -> SkillResult:
        starts_after, starts_before = self._date_window(context.intent)
        is_lifeops = "plan my" in (context.intent or "").casefold() or "itinerary" in (
            context.intent or ""
        ).casefold()
        listings = self.provider.discover(
            query=None if is_lifeops else entities.get("location"),
            starts_after=starts_after,
            starts_before=starts_before,
            category=entities.get("category"),
            latitude=(context.current_place.latitude if context.current_place else None),
            longitude=(context.current_place.longitude if context.current_place else None),
        )
        if starts_before is not None and not (
            is_lifeops and context.current_place is not None
        ):
            listings = sorted(
                listings,
                key=lambda item: (
                    item.starts_at.date() < starts_after.date(),
                    item.starts_at,
                ),
            )
        if is_lifeops:
            listings = listings[:3]
        if not listings:
            return SkillResult(
                success=False,
                summary=(
                    "No matching upcoming events were found in Aug9's governed "
                    "sources. You can browse these external event guides."
                ),
                actions=[
                    SkillAction(
                        type="open_url",
                        label=label,
                        url=url,
                        metadata={
                            "capability": "events",
                            "source_access": "link_only",
                        },
                    )
                    for label, url in EVENT_SOURCE_LINKS
                ],
            )
        return SkillResult(
            success=True,
            data={"events": [item.model_dump(mode="json") for item in listings]},
            summary="Upcoming events: " + ", ".join(item.name for item in listings) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"View {item.name}",
                    url=item.booking_url or item.source_url,
                    metadata={"capability": "events", "event": item.name},
                )
                for item in listings
            ],
        )

    @staticmethod
    def _date_window(intent: str | None) -> tuple[datetime, datetime | None]:
        now = datetime.now(UTC)
        text = (intent or "").casefold()
        if "this weekend" in text or "weekend" in text:
            days_until_saturday = (5 - now.weekday()) % 7
            start = (now + timedelta(days=days_until_saturday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return start, start + timedelta(days=2)
        for weekday_name, weekday_number in (("saturday", 5), ("sunday", 6)):
            if weekday_name in text:
                days_until_weekday = (weekday_number - now.weekday()) % 7
                start = (now + timedelta(days=days_until_weekday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                return start, start + timedelta(days=1)
        if "today" in text:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, start + timedelta(days=1)
        if "tomorrow" in text:
            start = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return start, start + timedelta(days=1)
        return now, None
