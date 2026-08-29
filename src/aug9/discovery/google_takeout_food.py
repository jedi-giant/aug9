from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from aug9.discovery.food_domain import FoodDomainDocument


def convert_google_takeout_food(
    paths: list[Path],
    *,
    output_path: Path,
) -> tuple[int, int]:
    """Create a privacy-minimised SG food-domain file from owner-supplied exports."""
    places: dict[tuple[str, float, float], dict[str, Any]] = {}
    skipped = 0
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for feature in payload.get("features", []):
            properties = feature.get("properties") or {}
            location = properties.get("location") or {}
            coordinates = (feature.get("geometry") or {}).get("coordinates") or []
            if (
                len(coordinates) < 2
                or not (103.6 <= coordinates[0] <= 104.1)
                or not (1.1 <= coordinates[1] <= 1.5)
                or not location.get("name")
            ):
                skipped += 1
                continue
            name = " ".join(str(location["name"]).split())
            address = " ".join(str(location.get("address") or "").split()) or None
            key = (
                re.sub(r"[^a-z0-9]", "", name.casefold()),
                round(float(coordinates[1]), 5),
                round(float(coordinates[0]), 5),
            )
            maps_url = properties.get("google_maps_url")
            external_id = hashlib.sha256(
                f"{name.casefold()}|{coordinates[1]:.6f}|{coordinates[0]:.6f}".encode()
            ).hexdigest()[:24]
            postal_match = re.search(r"(?<!\d)(\d{6})(?!\d)", address or "")
            places.setdefault(
                key,
                {
                    "external_id": external_id,
                    "entity_type": "food_venue",
                    "name": name,
                    "description": None,
                    "status": "active",
                    "location": {
                        "address": address,
                        "postal_code": postal_match.group(1) if postal_match else None,
                        "latitude": coordinates[1],
                        "longitude": coordinates[0],
                        "unit_number": None,
                        "neighbourhood": None,
                    },
                    "parent": None,
                    "food_profile": {
                        "venue_kind": "restaurant",
                        "cuisines": [],
                        "signature_dishes": [],
                        "dietary_attributes": [],
                        "price": {
                            "currency": "SGD",
                            "minimum": None,
                            "maximum": None,
                        },
                        "reservation_url": None,
                    },
                    "opening_hours": [],
                    "contact": {"google_maps_url": maps_url} if maps_url else {},
                    "attributes": {"requires_food_type_verification": True},
                    "evidence": [],
                    "provenance": {
                        "source_url": maps_url,
                        "observed_at": "2026-08-29T12:00:00+08:00",
                        "verified_at": None,
                        "notes": (
                            "Imported from a private Google Maps export with personal "
                            "activity fields removed; food type requires verification."
                        ),
                    },
                },
            )

    document = {
        "schema_version": "aug9.food-domain.v1",
        "generated_at": "2026-08-29T12:00:00+08:00",
        "source": {
            "id": "jd_google_maps_food_places",
            "name": "JD Google Maps Food Places",
            "permission": "user_provided",
            "attribution": (
                "Private user-provided Google Maps export; review text, ratings, "
                "comments, and activity dates removed"
            ),
        },
        "places": list(places.values()),
    }
    FoodDomainDocument.model_validate(document)
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(places), skipped
