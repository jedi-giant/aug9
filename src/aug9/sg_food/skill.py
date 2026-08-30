import os
import sqlite3
from typing import Any
from urllib.parse import quote_plus

import psycopg

from aug9.core.context import UserContext
from aug9.core.recommendation import RecommendationConstraints
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.food import get_food_recommendations
from aug9.sg_food.provider import FoodProvider, FoodVenue


MAX_COMFORTABLE_WALK_KM = 1.2


def configured_food_ranking_mode() -> str:
    value = os.getenv("FOOD_RANKING_MODE", "legacy").strip().casefold()
    return value if value in {"legacy", "shortlist"} else "legacy"


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
        requested_ranking_mode = configured_food_ranking_mode()
        ranking_mode = "legacy"
        shortlist_details: dict[str, dict[str, Any]] = {}
        venues = []
        if (
            requested_ranking_mode == "shortlist"
            and latitude is not None
            and longitude is not None
        ):
            try:
                from aug9.discovery.food_ranking_shadow import (
                    build_food_ranking_shadow_report,
                )

                report = build_food_ranking_shadow_report(
                    self.provider,
                    latitude=latitude,
                    longitude=longitude,
                    venue_kinds=venue_kinds,
                    pool_limit=250,
                    display_limit=3,
                    request_text=context.intent or "food",
                )
                shortlist = report["recommended_shortlist"]
                if shortlist:
                    venues = [
                        self._shortlist_venue(item) for item in shortlist
                    ]
                    shortlist_details = {
                        item["entity_id"]: item for item in shortlist
                    }
                    ranking_mode = "shortlist"
            except (psycopg.Error, sqlite3.Error):
                venues = []
        if ranking_mode == "legacy":
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
            recommendation = shortlist_details.get(venue.id, {})
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
                    "safe_grade_evidence": (
                        "Singapore Food Agency" if venue.safe_grade else "unknown"
                    ),
                    "licensing_evidence": (
                        "Singapore Food Agency"
                        if venue.catalog_basis == "sfa_licensed"
                        else "not independently verified"
                    ),
                    "catalog_basis": venue.catalog_basis,
                    "location_evidence": "OneMap",
                    "taste_evidence": (
                        "active organic editorial evidence"
                        if recommendation.get(
                            "positive_organic_editorial_records", 0
                        )
                        else "unknown"
                    ),
                    "opening_hours_evidence": "unknown",
                    "price_evidence": "unknown",
                    "dietary_evidence": "unknown",
                    "recommendation_role": recommendation.get("role"),
                    "recommendation_reason": recommendation.get("reason"),
                    "ranking_score": recommendation.get("proposed_score"),
                    "editorial_food_quality_records": recommendation.get(
                        "positive_organic_editorial_records", 0
                    ),
                    "editorial_sources": recommendation.get(
                        "editorial_sources", []
                    ),
                }
            )

        has_standalone = any(
            place.get("catalog_basis") == "editorial_standalone"
            for place in places
        )
        disclosures = [
            (
                "SAFE grades, where shown, describe food-safety records, "
                "not taste or popularity"
            ),
            "I haven't yet verified opening hours, prices or dietary suitability",
        ]
        if has_standalone:
            disclosures.append(
                "editorial picks without a SAFE grade have not yet been "
                "independently matched to an SFA licence"
            )
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
                "ranking_mode": ranking_mode,
                "ranking_mode_requested": requested_ranking_mode,
                "result_limit": 3 if ranking_mode == "shortlist" else len(places),
            },
            summary=(
                self._natural_summary(places, ranking_mode)
                + " "
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
                        "ranking_mode": ranking_mode,
                        "recommendation_role": place["recommendation_role"],
                    },
                )
                for place in places
            ],
        )

    @classmethod
    def _natural_summary(
        cls, places: list[dict[str, Any]], ranking_mode: str
    ) -> str:
        if ranking_mode == "shortlist":
            introductions = [
                "My closest suitable pick is",
                "For a little variety, consider",
                "Another nearby option is",
            ]
            sentences = []
            for index, place in enumerate(places):
                detail = cls._friendly_distance(place["distance_km"])
                reason = str(place.get("recommendation_reason") or "").strip()
                suffix = ", ".join(value for value in (detail, reason) if value)
                sentences.append(
                    f'{introductions[min(index, len(introductions) - 1)]} '
                    f'{place["name"]}{f" — {suffix}" if suffix else ""}.'
                )
            scope = (
                "well-supported food options"
                if any(
                    place.get("catalog_basis") == "editorial_standalone"
                    for place in places
                )
                else "licensed food options"
            )
            return f"Here are a few {scope} nearby. " + " ".join(sentences)

        names = [place["name"] for place in places]
        if len(names) == 1:
            joined = names[0]
        else:
            joined = ", ".join(names[:-1]) + f", or {names[-1]}"
        return f"I found these licensed food options nearby: {joined}."

    @staticmethod
    def _friendly_distance(distance_km: float | None) -> str:
        if distance_km is None:
            return ""
        if distance_km < 0.1:
            return "less than 100 m away"
        if distance_km < 1:
            return f"about {round(distance_km * 10) * 100:.0f} m away"
        return f"about {distance_km:.1f} km away"

    @staticmethod
    def _shortlist_venue(item: dict[str, Any]) -> FoodVenue:
        return FoodVenue(
            id=item["entity_id"],
            name=item["name"],
            venue_kind=item["venue_kind"],
            address=item["address"],
            postal_code=item["postal_code"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            safe_grade=item["safe_grade"],
            business_type=item["business_type"],
            distance_km=item["distance_km"],
            catalog_basis=item["catalog_basis"],
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
