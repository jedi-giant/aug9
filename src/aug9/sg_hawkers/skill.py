import math
import re
from datetime import datetime, time
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from aug9.core.context import UserContext
from aug9.core.recommendation import (
    RecommendationCandidate,
    RecommendationConstraints,
    RecommendationEngine,
)
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_hawkers.provider import HawkerProvider, distance_km


MAX_COMFORTABLE_WALK_KM = 1.2


class SgHawkersSkill(Aug9Skill):
    name = "sg_hawkers"
    description = "Discover active Singapore hawker centres from governed data"
    version = "0.1.0"

    def __init__(self, provider: HawkerProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["hawkers"]

    def execute(
        self,
        context: UserContext,
        entities: dict[str, Any],
    ) -> SkillResult:
        query = entities.get("location") or self._extract_location(context.intent)
        constraints = RecommendationConstraints.from_entities(entities)
        verified_listings = self._verified_food_matches(context, constraints)
        if verified_listings:
            return self._verified_listing_result(context, constraints, verified_listings)
        if (
            context.current_place is not None
            and context.current_place.latitude is not None
            and context.current_place.longitude is not None
        ):
            places = self.provider.discover_near(
                context.current_place.latitude,
                context.current_place.longitude,
            )
        else:
            places = self.provider.discover(str(query) if query else None)
        if not places:
            return SkillResult(
                success=False,
                summary="No matching active hawker centres were found.",
            )

        ranked_places = []
        for place in places:
            item = place.model_dump()
            if constraints.budget_sgd is not None:
                item["price_evidence"] = "unknown"
            if constraints.open_now:
                item["opening_hours_evidence"] = "unknown"
            if (
                context.current_place is not None
                and context.current_place.latitude is not None
                and context.current_place.longitude is not None
            ):
                calculated_distance = distance_km(
                    context.current_place.latitude,
                    context.current_place.longitude,
                    place,
                )
                if math.isfinite(calculated_distance):
                    item["distance_km"] = round(calculated_distance, 1)
            ranked_places.append(item)

        summary_items = []
        for item in ranked_places:
            distance = item.get("distance_km")
            if distance is None:
                summary_items.append(item["name"])
                continue
            travel_guidance = (
                "walking may be practical"
                if distance <= MAX_COMFORTABLE_WALK_KM
                else "consider public transport"
            )
            summary_items.append(
                f'{item["name"]} ({distance:.1f} km away; {travel_guidance})'
            )

        disclosures = []
        if self._constraints_requested(constraints):
            disclosures.append(
                "No stall-level records met every verified constraint; these are nearby centres, not verified matches"
            )
        if constraints.budget_sgd is not None:
            disclosures.append(
                f"Prices are not verified, so confirm options fit the S${constraints.budget_sgd:g} budget"
            )
        if constraints.dietary_preferences:
            disclosures.append(
                "Dietary suitability is not verified; confirm "
                + "/".join(constraints.dietary_preferences)
                + " requirements with the stall"
            )
        if constraints.open_now:
            disclosures.append("Opening hours are not verified; check before travelling")
        disclosure_text = " " + ". ".join(disclosures) + "." if disclosures else ""

        return SkillResult(
            success=True,
            data={
                "places": ranked_places,
                "constraints": constraints.model_dump(),
            },
            summary=(
                "Nearby hawker centres: "
                + ", ".join(summary_items)
                + "."
                + disclosure_text
            ),
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"Get directions to {place.name}",
                    url=(
                        "https://www.google.com/maps/dir/?api=1"
                        f"&destination={quote_plus(place.name)}"
                    ),
                    metadata={
                        "capability": "hawkers",
                        "place": place.name,
                        "distance_km": ranked_places[index].get("distance_km"),
                    },
                )
                for index, place in enumerate(places)
            ],
        )

    def _verified_food_matches(
        self,
        context: UserContext,
        constraints: RecommendationConstraints,
    ):
        if not self._constraints_requested(constraints):
            return []
        listings = self.provider.food_listings()
        candidates = []
        listings_by_id = {}
        for listing in listings:
            profile = listing.profile
            location = listing.parent or listing.entity
            calculated_distance = None
            if (
                context.current_place is not None
                and context.current_place.latitude is not None
                and context.current_place.longitude is not None
            ):
                value = distance_km(
                    context.current_place.latitude,
                    context.current_place.longitude,
                    location,
                )
                if math.isfinite(value):
                    calculated_distance = value
            candidate = RecommendationCandidate(
                id=listing.entity.id,
                title=listing.entity.name,
                distance_km=calculated_distance,
                price_max=profile.price_max,
                attributes=profile.dietary_attributes,
                attributes_verified=True,
                open_now=(
                    self._is_open_now(listing.opening_periods)
                    if listing.opening_periods
                    else None
                ),
                relevance_score=0.8,
                provenance_score=1.0,
                freshness_score=0.5,
            )
            candidates.append(candidate)
            listings_by_id[candidate.id] = listing
        outcome = RecommendationEngine().rank(candidates, constraints, limit=5)
        return [
            (listings_by_id[item.candidate.id], item)
            for item in outcome.ranked
        ]

    def _verified_listing_result(self, context, constraints, listings) -> SkillResult:
        ranked = []
        for listing, ranking in listings:
            location = listing.parent or listing.entity
            item = {
                "name": listing.entity.name,
                "centre_name": listing.parent.name if listing.parent else None,
                "address": location.address,
                "postal_code": location.postal_code,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "price_min": listing.profile.price_min,
                "price_max": listing.profile.price_max,
                "currency": listing.profile.currency,
                "price_evidence": "verified_source",
                "dietary_attributes": listing.profile.dietary_attributes,
                "dietary_evidence": "verified_source",
                "opening_hours_evidence": (
                    "verified_source" if listing.opening_periods else "unknown"
                ),
                "tags": listing.tags,
                "ranking_score": ranking.total_score,
                "confidence": ranking.confidence.value,
                "ranking_factors": [
                    factor.model_dump() for factor in ranking.factors
                ],
            }
            if (
                context.current_place is not None
                and context.current_place.latitude is not None
                and context.current_place.longitude is not None
            ):
                calculated = distance_km(
                    context.current_place.latitude,
                    context.current_place.longitude,
                    location,
                )
                if math.isfinite(calculated):
                    item["distance_km"] = round(calculated, 1)
            ranked.append(item)
        ranked.sort(key=lambda item: item.get("distance_km", math.inf))

        descriptions = []
        for item in ranked:
            details = []
            if item.get("distance_km") is not None:
                details.append(f'{item["distance_km"]:.1f} km away')
            if item.get("price_max") is not None:
                details.append(f'up to S${item["price_max"]:g}')
            if constraints.dietary_preferences:
                details.append("verified " + "/".join(constraints.dietary_preferences))
            descriptions.append(
                item["name"] + (f" ({'; '.join(details)})" if details else "")
            )

        return SkillResult(
            success=True,
            data={"places": ranked, "constraints": constraints.model_dump()},
            summary="Verified food matches: " + ", ".join(descriptions) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f'Get directions to {item["name"]}',
                    url=(
                        "https://www.google.com/maps/dir/?api=1&destination="
                        + quote_plus(
                            " ".join(
                                value
                                for value in (item["name"], item.get("centre_name"))
                                if value
                            )
                        )
                    ),
                    metadata={
                        "capability": "hawkers",
                        "place": item["name"],
                        "distance_km": item.get("distance_km"),
                    },
                )
                for item in ranked
            ],
        )

    @staticmethod
    def _constraints_requested(constraints: RecommendationConstraints) -> bool:
        return bool(
            constraints.budget_sgd is not None
            or constraints.dietary_preferences
            or constraints.open_now
        )

    @staticmethod
    def _is_open_now(periods) -> bool:
        now = datetime.now(ZoneInfo("Asia/Singapore"))
        current = now.time().replace(tzinfo=None)
        for period in periods:
            if period.day_of_week != now.weekday():
                continue
            opens_at = time.fromisoformat(period.opens_at)
            closes_at = time.fromisoformat(period.closes_at)
            if opens_at <= closes_at and opens_at <= current <= closes_at:
                return True
            if opens_at > closes_at and (current >= opens_at or current <= closes_at):
                return True
        return False

    @staticmethod
    def _extract_location(intent: str | None) -> str | None:
        if not intent:
            return None
        match = re.search(
            r"\b(?:near|around|at)\s+(.+?)(?:[?.!]|$)",
            intent,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else None
