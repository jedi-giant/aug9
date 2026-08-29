import json

from aug9.core import database
from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.discovery.models import EntityType
from aug9.discovery.playgrounds import PlaygroundGeoJsonImporter
from aug9.discovery.repository import DiscoveryRepository
from aug9.sg_playgrounds import DatabasePlaygroundProvider, SgPlaygroundsSkill


def playground_feature(
    feature_id=1,
    name="Neighbourhood Playground",
    longitude=103.8,
    latitude=1.3,
    *,
    min_age=2,
    max_age=12,
    water_play=False,
    sheltered=False,
):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "id": feature_id,
            "name": name,
            "address": "1 Example Road, Singapore 123456",
            "theme": "Nature play",
            "age_fit": "2–12 years",
            "min_age": min_age,
            "max_age": max_age,
            "features": ["Swings", "Slides"],
            "has_water_play": water_play,
            "is_sheltered": sheltered,
            "sources": "NParks / PlaySG / OneMap",
        },
    }


def test_playground_importer_normalises_user_geojson():
    entity, record, provenance = PlaygroundGeoJsonImporter.normalise(playground_feature())

    assert entity.entity_type == EntityType.PLAYGROUND
    assert entity.name == "Neighbourhood Playground"
    assert record.raw_payload["properties"]["features"] == ["Swings", "Slides"]
    assert {item.field_name for item in provenance} >= {"name", "latitude", "longitude"}


def test_playground_import_and_nearby_skill(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "playgrounds.db")
    database.initialise_database()
    path = tmp_path / "playgrounds.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    playground_feature(),
                    playground_feature(2, "Far Playground", 103.95, 1.42),
                ],
            }
        ),
        encoding="utf-8",
    )
    summary = PlaygroundGeoJsonImporter(DiscoveryRepository()).run(path)

    result = SgPlaygroundsSkill(DatabasePlaygroundProvider(limit=2)).execute(
        UserContext(
            intent="Find a playground near me",
            current_place=Place(name="Here", latitude=1.3001, longitude=103.8001),
        ),
        {},
    )

    assert summary.upserted == 2
    assert result.success is True
    assert result.data["playgrounds"][0]["name"] == "Neighbourhood Playground"
    assert result.data["playgrounds"][0]["age_fit"] == "2–12 years"
    assert "2–12 years" in result.summary
    assert result.actions[0].metadata["capability"] == "playgrounds"


def test_playground_skill_filters_age_and_water_play(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "filtered.db")
    database.initialise_database()
    path = tmp_path / "playgrounds.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    playground_feature(1, "Dry Toddler Park", max_age=5),
                    playground_feature(
                        2,
                        "Water Family Park",
                        103.801,
                        1.301,
                        max_age=12,
                        water_play=True,
                    ),
                ],
            }
        ),
        encoding="utf-8",
    )
    PlaygroundGeoJsonImporter(DiscoveryRepository()).run(path)

    result = SgPlaygroundsSkill(DatabasePlaygroundProvider()).execute(
        UserContext(
            intent="Find a water playground for my 8-year-old near me",
            current_place=Place(name="Here", latitude=1.3, longitude=103.8),
        ),
        {"child_ages": [8], "water_play": True},
    )

    assert result.success is True
    assert [item["name"] for item in result.data["playgrounds"]] == [
        "Water Family Park"
    ]
    assert result.data["filters"]["child_ages"] == [8]
    assert "water play" in result.summary


def test_playground_skill_prioritises_shelter_for_rain(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "rain.db")
    database.initialise_database()
    path = tmp_path / "playgrounds.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    playground_feature(1, "Closer Open Park"),
                    playground_feature(
                        2, "Sheltered Park", 103.81, 1.31, sheltered=True
                    ),
                ],
            }
        ),
        encoding="utf-8",
    )
    PlaygroundGeoJsonImporter(DiscoveryRepository()).run(path)

    result = SgPlaygroundsSkill(DatabasePlaygroundProvider(limit=2)).execute(
        UserContext(
            intent="Find a playground near me if it rains",
            current_place=Place(name="Here", latitude=1.3, longitude=103.8),
        ),
        {},
    )

    assert result.data["playgrounds"][0]["name"] == "Sheltered Park"
    assert result.data["filters"]["weather_aware_shelter_preference"] is True
