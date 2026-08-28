from typing import Any
from urllib.parse import quote_plus

from aug9.core.context import UserContext
from aug9.core.recommendation import RecommendationConstraints
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.food import get_food_recommendations
from aug9.sg_food.provider import FoodProvider


MAX_COMFORTABLE_WALK_KM = 1.2


class SgFoodSkill(Aug9Skill):
    name = "sg_food"
    description = "Discover nearby licensed Singapore food establishments"
    version = "0.1.0"

    def __init__(self, provider: FoodProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["food"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        constraints = RecommendationConstraints.from_entities(entities)
        venue_kinds = self._venue_kinds(context.intent or "")
        current_place = context.current_place
        latitude = current_place.latitude if current_place else None
        longitude = current_place.longitude if current_place else None
        query = None if latitude is not None and longitude is not None else entities.get("location")
        if latitude is None or longitude is None:
            if not query:
                return SkillResult(
                    success=False,
                    summary="Share a starting location so I can find nearby licensed food establishments.",
                )
        if self._requests_cafe(context.intent or ""):
            return SkillResult(
                success=False,
                summary=(
                    "The current SFA evidence does not reliably distinguish cafés from other "
                    "restaurants yet. Ask for nearby restaurants, or share a café source for verification."
                ),
            )
        venues = self.provider.discover(
            latitude=latitude,
            longitude=longitude,
            query=str(query) if query else None,
            venue_kinds=venue_kinds,
        )
        if not venues:
            legacy = self._legacy_result(context)
            if legacy is not None:
                return legacy
            return SkillResult(
                success=False,
                summary=(
                    "I couldn't find a matching licensed food establishment nearby."
                    if latitude is not None and longitude is not None
                    else "Share a starting location so I can find nearby licensed food establishments."
                ),
            )

        places = []
        for venue in venues:
            travel_guidance = None
            if venue.distance_km is not None:
                travel_guidance = (
                    "walking may be practical"
                    if venue.distance_km <= MAX_COMFORTABLE_WALK_KM
                    else "consider public transport or a short ride"
                )
            places.append(
                {
                    "id": venue.id,
                    "name": venue.name,
                    "venue_kind": venue.venue_kind,
                    "address": venue.address,
                    "postal_code": venue.postal_code,
                    "latitude": venue.latitude,
                    "longitude": venue.longitude,
                    "distance_km": venue.distance_km,
                    "travel_guidance": travel_guidance,
                    "safe_grade": venue.safe_grade,
                    "safe_grade_evidence": "Singapore Food Agency",
                    "licensing_evidence": "Singapore Food Agency",
                    "location_evidence": "OneMap",
                    "taste_evidence": "unknown",
                    "opening_hours_evidence": "unknown",
                    "price_evidence": "unknown",
                    "dietary_evidence": "unknown",
                }
            )

        descriptions = []
        for place in places:
            details = [place["venue_kind"].replace("_", " ")]
            if place["distance_km"] is not None:
                details.append(f'{place["distance_km"]:.1f} km away')
            details.append(f'SFA SAFE grade {place["safe_grade"]}')
            descriptions.append(f'{place["name"]} ({"; ".join(details)})')

        disclosures = [
            "SAFE grades describe regulatory food-safety track records, not taste or popularity",
            "opening hours, prices and dietary suitability are not yet verified",
        ]
        if constraints.open_now:
            disclosures.append("I cannot yet verify which results are open now")
        if constraints.budget_sgd is not None:
            disclosures.append(
                f'I cannot yet verify the S${constraints.budget_sgd:g} budget'
            )
        if constraints.dietary_preferences:
            disclosures.append(
                "confirm " + "/".join(constraints.dietary_preferences) + " suitability directly"
            )

        return SkillResult(
            success=True,
            data={
                "places": places,
                "constraints": constraints.model_dump(),
                "evidence_scope": {
                    "verified": ["licensing", "safe_grade", "location"],
                    "unknown": ["taste", "opening_hours", "price", "dietary"],
                },
            },
            summary=(
                "Nearby licensed food options: "
                + ", ".join(descriptions)
                + ". "
                + ". ".join(disclosures)
                + "."
            ),
            actions=[
                SkillAction(
                    type="open_url",
                    label=f'Get directions to {place["name"]}',
                    url=(
                        "https://www.google.com/maps/dir/?api=1&destination="
                        + quote_plus(
                            ", ".join(
                                value
                                for value in (place["name"], place["address"])
                                if value
                            )
                        )
                    ),
                    metadata={
                        "capability": "food",
                        "place": place["name"],
                        "distance_km": place["distance_km"],
                    },
                )
                for place in places
            ],
        )

    @staticmethod
    def _legacy_result(context: UserContext) -> SkillResult | None:
        if context.current_place is None:
            return None
        preferences = []
        if context.memory is not None:
            preferences = context.memory.preferences.get("food", [])
        result = get_food_recommendations(context.current_place.name, preferences)
        if not result.recommendations:
            return None
        places = [
            {
                "name": item.name,
                "description": item.description,
                "address": item.place.address,
                "postal_code": item.place.postal_code,
                "latitude": item.place.latitude,
                "longitude": item.place.longitude,
                "catalog_evidence": "legacy_beta_catalog",
            }
            for item in result.recommendations
        ]
        return SkillResult(
            success=True,
            data={"places": places, "evidence_scope": {"legacy_beta_fallback": True}},
            summary="You can try: " + ", ".join(item["name"] for item in places) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f'Get directions to {item["name"]}',
                    url=(
                        "https://www.google.com/maps/search/?api=1&query="
                        + quote_plus(
                            f'{item["name"]}, {context.current_place.name}'
                        )
                    ),
                    metadata={"capability": "food", "place": item["name"]},
                )
                for item in places
            ],
        )

    @staticmethod
    def _venue_kinds(intent: str) -> tuple[str, ...]:
        lowered = intent.casefold()
        if any(word in lowered for word in ("restaurant", "restaurants")):
            return ("restaurant",)
        if "hawker stall" in lowered or "hawker food" in lowered:
            return ("hawker_stall",)
        if any(word in lowered for word in ("food court", "foodcourt")):
            return ("food_court_stall",)
        return ()

    @staticmethod
    def _requests_cafe(intent: str) -> bool:
        lowered = intent.casefold()
        return any(word in lowered for word in ("cafe", "café", "cafes", "cafés"))
