import json
from copy import deepcopy
from pathlib import Path

from aug9.discovery.curate_food_domain import (
    curate_food_domain_payload,
    extract_venue_name,
)


def example_payload():
    return json.loads(
        (Path(__file__).parents[1] / "data" / "food_domain_v1.example.json")
        .read_text(encoding="utf-8")
    )


def test_extracts_venue_name_without_discarding_brand_words():
    assert extract_venue_name(
        "Fai Kee Fishhead Bee Hoon: 50-Year-Old Cantonese Zi Char Stall"
    ) == "Fai Kee Fishhead Bee Hoon"
    assert extract_venue_name(
        "LINKUS Opens Stunning New Takashimaya Outlet"
    ) == "LINKUS"
    assert extract_venue_name(
        "So Good Bakery Has Been Around For 9 Years—Here's Our Review"
    ) == "So Good Bakery"
    assert extract_venue_name(
        "Kuan Zhai Alley - Modern Authentic Sichuan Restaurant"
    ) == "Kuan Zhai Alley"


def test_removes_overseas_and_keeps_multi_location_records():
    payload = example_payload()
    base = payload["places"][0]
    base["name"] = "Where to find Example Restaurant outlets"
    base["location"]["address"] = "Mall A | Mall B, Singapore 123456"

    overseas = deepcopy(base)
    overseas["external_id"] = "overseas"
    overseas["location"] = {"address": "Jalan Molek, Johor, Malaysia"}
    payload["places"].append(overseas)

    roundup = deepcopy(base)
    roundup["external_id"] = "roundup"
    roundup["name"] = "Where to eat dim sum in Singapore"
    roundup["location"]["address"] = "1 Example Street, Singapore 123456"
    payload["places"].append(roundup)

    curated, quarantine, summary = curate_food_domain_payload(payload)

    assert len(curated["places"]) == 1
    assert curated["places"][0]["name"] == "Where to find Example Restaurant outlets"
    assert {item["reason"] for item in quarantine} == {
        "overseas_location", "non_venue_article"
    }
    assert summary.multi_location_records_kept == 1
