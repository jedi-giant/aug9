import json
from pathlib import Path

from aug9.discovery.prepare_food_domain import normalize_food_domain_payload


def test_normalizes_restaurants_and_unparented_stalls():
    payload = json.loads(
        (Path(__file__).parents[1] / "data" / "food_domain_v1.example.json")
        .read_text(encoding="utf-8")
    )
    restaurant = payload["places"][0]
    restaurant["entity_type"] = "restaurant"
    restaurant["food_profile"]["venue_kind"] = None
    stall = {
        **restaurant,
        "external_id": "standalone-stall",
        "entity_type": "food_stall",
        "parent": None,
        "food_profile": {**restaurant["food_profile"], "venue_kind": None},
    }
    payload["places"].append(stall)

    normalized, rejected, summary = normalize_food_domain_payload(payload)

    assert [place["entity_type"] for place in normalized["places"]] == [
        "food_venue", "food_venue"
    ]
    assert normalized["places"][0]["food_profile"]["venue_kind"] == "restaurant"
    assert normalized["places"][1]["food_profile"]["venue_kind"] == "food_stall"
    assert summary.restaurant_types_normalized == 1
    assert summary.unparented_stalls_normalized == 1
    assert summary.venue_kinds_filled == 2
    assert summary.accepted == 2
    assert rejected == []
