import argparse
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aug9.discovery.food_domain import FoodDomainDocument


@dataclass(frozen=True)
class FoodDomainPreparationSummary:
    received: int
    accepted: int
    rejected_missing_location: int
    restaurant_types_normalized: int
    unparented_stalls_normalized: int
    venue_kinds_filled: int
    prices_defaulted: int
    identifiers_shortened: int
    opening_periods_removed: int
    provenance_notes_truncated: int


def normalize_food_domain_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], FoodDomainPreparationSummary]:
    """Conservatively adapt a user collection to aug9.food-domain.v1."""
    normalized = deepcopy(payload)
    restaurant_types = unparented_stalls = venue_kinds = 0
    prices_defaulted = identifiers_shortened = opening_periods_removed = 0
    provenance_notes_truncated = 0
    accepted_places = []
    rejected_places = []

    for place in normalized.get("places", []):
        location = place.get("location") or {}
        if not any((
            location.get("address"),
            location.get("postal_code"),
            location.get("latitude") is not None,
        )):
            rejected_places.append({
                "reason": "missing_location",
                "place": place,
            })
            continue

        original_type = place.get("entity_type")
        if original_type == "restaurant":
            place["entity_type"] = "food_venue"
            restaurant_types += 1
        elif original_type == "food_stall" and place.get("parent") is None:
            # A stall relationship must name a real parent. Keep the record as
            # a standalone food venue rather than manufacturing that link.
            place["entity_type"] = "food_venue"
            unparented_stalls += 1

        profile = place.get("food_profile")
        if profile is not None and not profile.get("venue_kind"):
            profile["venue_kind"] = (
                "food_stall" if original_type == "food_stall" else "restaurant"
            )
            venue_kinds += 1
        if profile is not None and profile.get("price") is None:
            profile["price"] = {"currency": "SGD"}
            prices_defaulted += 1

        if len(place.get("external_id", "")) > 160:
            place["external_id"] = _bounded_identifier(place["external_id"])
            identifiers_shortened += 1
        for evidence in place.get("evidence", []):
            if len(evidence.get("external_id", "")) > 160:
                evidence["external_id"] = _bounded_identifier(
                    evidence["external_id"]
                )
                identifiers_shortened += 1

        periods = place.get("opening_hours", [])
        unique_periods = list({
            (
                period.get("day_of_week"),
                period.get("opens_at"),
                period.get("closes_at"),
            ): period
            for period in periods
        }.values())[:40]
        opening_periods_removed += len(periods) - len(unique_periods)
        place["opening_hours"] = unique_periods
        provenance = place.get("provenance") or {}
        notes = provenance.get("notes")
        if notes and len(notes) > 1000:
            provenance["notes"] = notes[:1000]
            provenance_notes_truncated += 1
        accepted_places.append(place)

    normalized["places"] = accepted_places

    # Validation is deliberately performed before writing or importing.
    document = FoodDomainDocument.model_validate(normalized)
    canonical = document.model_dump(mode="json", exclude_none=True)
    return canonical, rejected_places, FoodDomainPreparationSummary(
        received=len(accepted_places) + len(rejected_places),
        accepted=len(document.places),
        rejected_missing_location=len(rejected_places),
        restaurant_types_normalized=restaurant_types,
        unparented_stalls_normalized=unparented_stalls,
        venue_kinds_filled=venue_kinds,
        prices_defaulted=prices_defaulted,
        identifiers_shortened=identifiers_shortened,
        opening_periods_removed=opening_periods_removed,
        provenance_notes_truncated=provenance_notes_truncated,
    )


def _bounded_identifier(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{value[:143]}-{digest}"


def prepare_food_domain(
    input_path: Path,
    output_path: Path,
    rejected_output_path: Path | None = None,
) -> FoodDomainPreparationSummary:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    normalized, rejected, summary = normalize_food_domain_payload(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    if rejected_output_path is not None:
        rejected_output_path.parent.mkdir(parents=True, exist_ok=True)
        rejected_output_path.write_text(
            json.dumps(
                {
                    "generated_at": payload.get("generated_at"),
                    "source": payload.get("source"),
                    "rejected": rejected,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and normalize a collection for Aug9 food-domain import"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rejected-output", type=Path)
    args = parser.parse_args()
    summary = prepare_food_domain(
        args.input, args.output, args.rejected_output
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
