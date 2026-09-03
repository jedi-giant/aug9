import argparse
import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aug9.discovery.food_domain import FoodDomainDocument


OVERSEAS_MARKERS = re.compile(
    r"\b(?:malaysia|johor|kuala lumpur|melaka|malacca|taiwan|taipei|taichung|"
    r"thailand|bangkok|indonesia|jakarta|bali|vietnam|ho chi minh|hanoi|"
    r"philippines|manila|hong kong|macau|japan|tokyo|osaka|south korea|seoul|"
    r"chengdu|shanghai|beijing|guangzhou|busan)\b",
    re.IGNORECASE,
)
NON_VENUE_PREFIXES = re.compile(
    r"^(?:where to|guide to|a guide to|the best\b|best\b|\d+\s+(?:best|places|restaurants)|"
    r"\d+\s+(?:famous|food deals?|new openings?)|what to eat|things to eat|"
    r"food guide\b|dining guide\b|new restaurants?\b|this\b|we\b|you can\b|"
    r"get \$|found\b|first look\b|build your own\b|amazing\b|is\b)",
    re.IGNORECASE,
)
HEADLINE_ACTIONS = re.compile(
    r"\s+(?:opens?|returns?|brings?|launches?|introduces?|celebrates?|serves?|"
    r"unveils?|reopens?|debuts?|lands?|arrives?|has|have|is|draws?|offers?|gets?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FoodDomainCurationSummary:
    received: int
    accepted: int
    overseas_removed: int
    non_venue_articles_quarantined: int
    venue_names_normalized: int
    multi_location_records_kept: int


def curate_food_domain_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], FoodDomainCurationSummary]:
    curated = deepcopy(payload)
    accepted = []
    quarantine = []
    overseas = non_venue = normalized_names = multi_location = 0

    for place in curated.get("places", []):
        address = str((place.get("location") or {}).get("address") or "")
        if OVERSEAS_MARKERS.search(address):
            quarantine.append({"reason": "overseas_location", "place": place})
            overseas += 1
            continue

        original_name = str(place.get("name") or "").strip()
        is_multi_location = "|" in address
        if not is_multi_location and (
            NON_VENUE_PREFIXES.search(original_name)
            or original_name.casefold().startswith("this new ")
        ):
            quarantine.append({"reason": "non_venue_article", "place": place})
            non_venue += 1
            continue

        venue_name = extract_venue_name(original_name)
        if venue_name != original_name:
            attributes = place.setdefault("attributes", {})
            attributes["editorial_headline"] = original_name
            place["name"] = venue_name
            normalized_names += 1
        if is_multi_location:
            multi_location += 1
        accepted.append(place)

    curated["places"] = accepted
    document = FoodDomainDocument.model_validate(curated)
    return (
        document.model_dump(mode="json", exclude_none=True),
        quarantine,
        FoodDomainCurationSummary(
            received=len(accepted) + len(quarantine),
            accepted=len(accepted),
            overseas_removed=overseas,
            non_venue_articles_quarantined=non_venue,
            venue_names_normalized=normalized_names,
            multi_location_records_kept=multi_location,
        ),
    )


def extract_venue_name(headline: str) -> str:
    candidates = [headline]
    for separator in (":", " — ", " – ", " - "):
        if separator in headline:
            candidates.append(headline.split(separator, 1)[0])
    action = HEADLINE_ACTIONS.search(headline)
    if action:
        candidates.append(headline[: action.start()])
    viable = [
        candidate.strip(" -–—:,.\t")
        for candidate in candidates
        if 2 <= len(candidate.strip(" -–—:,.\t")) <= 120
    ]
    if not viable:
        return headline
    # The shortest leading clause is normally the venue name; never infer
    # words that were not present in the supplied headline.
    return min(viable, key=len)


def curate_food_domain(
    input_path: Path, output_path: Path, quarantine_path: Path
) -> FoodDomainCurationSummary:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    curated, quarantine, summary = curate_food_domain_payload(payload)
    output_path.write_text(
        json.dumps(curated, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    quarantine_path.write_text(
        json.dumps(
            {
                "generated_at": payload.get("generated_at"),
                "source": payload.get("source"),
                "quarantined": quarantine,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Curate Singapore venues and editorial names before import"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--quarantine-output", required=True, type=Path)
    args = parser.parse_args()
    summary = curate_food_domain(
        args.input, args.output, args.quarantine_output
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
