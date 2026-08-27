import json

import pytest

from aug9.core import database
from aug9.discovery.food_candidates import (
    FoodCandidateImporter,
    FoodCandidateRepository,
)
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "candidates.db")
    database.initialise_database()
    return DiscoveryRepository(), FoodCandidateRepository()


def source(permission=SourcePermission.RESEARCH_ONLY):
    return DiscoverySource(
        id="community_food_seed",
        name="Community food seed",
        permission=permission,
        attribution="Community food contributors",
    )


def test_food_candidate_staging_keeps_only_factual_fields(repositories, tmp_path):
    repository, candidates = repositories
    path = tmp_path / "seed.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [103.84579, 1.28515, 0],
                        },
                        "properties": {
                            "name": "Ah Meng Kueh",
                            "description": (
                                "Address:<br>#02-45 Hong Lim Market & Food Centre"
                                "<br><br>Opening Hours:<br>Tues-Sat, 8.30am-6.30pm"
                                "<br><br>Shop Recommendations:<br>Peanut pancake; coconut pancake"
                                "<br><br>Other Details:<br>Personal narrative must not persist"
                                "<br><br>Contributor:<br>Named Person"
                                "<br><br>Facebook:<br>https://j.mp/example"
                            ),
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = FoodCandidateImporter(repository, candidates, source()).run(path)
    conn = database.get_connection()
    row = conn.execute(
        "SELECT name, address_text, opening_hours_text, dish_tags, status "
        "FROM discovery_food_candidates"
    ).fetchone()
    conn.close()

    assert summary.staged == 1
    assert summary.duplicates == 0
    assert row[0] == "Ah Meng Kueh"
    assert row[1] == "#02-45 Hong Lim Market & Food Centre"
    assert row[2] == "Tues-Sat, 8.30am-6.30pm"
    assert json.loads(row[3]) == ["Peanut pancake", "coconut pancake"]
    assert row[4] == "staged"
    assert "Personal narrative" not in " ".join(str(item) for item in row)
    assert "Named Person" not in " ".join(str(item) for item in row)
    assert "j.mp" not in " ".join(str(item) for item in row)


def test_food_candidate_staging_quarantines_closure_and_rejects_bad_geometry(
    repositories, tmp_path
):
    repository, candidates = repositories
    path = tmp_path / "seed.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [103.85, 1.29],
                        },
                        "properties": {
                            "name": "Former Stall",
                            "description": "Other Details:<br>Permanently closed",
                        },
                    },
                    {
                        "geometry": {
                            "type": "Point",
                            "coordinates": [0, 0],
                        },
                        "properties": {"name": "Outside Singapore"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = FoodCandidateImporter(repository, candidates, source()).run(path)

    assert summary.quarantined == 1
    assert summary.rejected == 1
    assert candidates.counts(source().id) == {"quarantined": 1}


def test_food_candidate_staging_reports_duplicate_identities(repositories, tmp_path):
    repository, candidates = repositories
    feature = {
        "geometry": {"type": "Point", "coordinates": [103.85, 1.29]},
        "properties": {"name": "Same Stall"},
    }
    path = tmp_path / "duplicates.geojson"
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature, feature]}),
        encoding="utf-8",
    )

    summary = FoodCandidateImporter(repository, candidates, source()).run(path)

    assert summary.received == 2
    assert summary.staged == 1
    assert summary.duplicates == 1


def test_food_candidate_staging_rejects_ingestable_partner_source(repositories):
    repository, candidates = repositories

    with pytest.raises(ValueError, match="research_only or legal_reviewed"):
        FoodCandidateImporter(
            repository,
            candidates,
            source(SourcePermission.LICENSED_PARTNER),
        )
