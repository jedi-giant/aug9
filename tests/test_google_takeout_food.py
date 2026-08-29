import json

from aug9.discovery.google_takeout_food import convert_google_takeout_food


def feature(name, longitude, latitude, **personal_fields):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "date": "2026-01-01T00:00:00Z",
            "google_maps_url": "https://maps.google.com/example",
            "location": {
                "name": name,
                "address": "1 Example Street, Singapore 123456",
                "country_code": "SG",
            },
            **personal_fields,
        },
    }


def test_takeout_conversion_keeps_place_facts_and_removes_personal_activity(tmp_path):
    source = tmp_path / "takeout.json"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    feature(
                        "Example Restaurant",
                        103.8,
                        1.3,
                        review_text_published="Personal review text",
                        five_star_rating_published=5,
                        Comment="Private comment",
                    ),
                    feature("Overseas Restaurant", 139.7, 35.6),
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "food.json"

    prepared, skipped = convert_google_takeout_food([source], output_path=output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    serialised = output.read_text(encoding="utf-8")

    assert prepared == 1
    assert skipped == 1
    assert payload["places"][0]["name"] == "Example Restaurant"
    assert payload["places"][0]["location"]["postal_code"] == "123456"
    assert "Personal review text" not in serialised
    assert "Private comment" not in serialised
    assert "five_star_rating_published" not in serialised
    assert "2026-01-01" not in serialised
