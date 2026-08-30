from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID
from aug9.sg_food import DatabaseFoodProvider, FoodVenue, SgFoodSkill
from aug9.sg_food.skill import configured_food_ranking_mode


class FakeFoodProvider:
    def __init__(self, venues):
        self.venues = venues
        self.calls = []

    def discover(self, **kwargs):
        self.calls.append(kwargs)
        return self.venues


@pytest.fixture
def food_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "sg-food.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA food establishments",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    conn = database.get_connection()
    cursor = conn.cursor()
    now = datetime.now(UTC).isoformat()
    for entity_id, name, kind, latitude, longitude in (
        ("food:near", "Nearby Noodles", "hawker_stall", 1.3005, 103.8005),
        ("food:far", "Far Restaurant", "restaurant", 1.4, 103.9),
    ):
        cursor.execute(
            "INSERT INTO discovery_entities "
            "(id, entity_type, name, address, postal_code, latitude, longitude, status, quality_score) "
            "VALUES (?, 'food_stall', ?, '1 Example Street Singapore 123456', "
            "'123456', ?, ?, 'active', 0.85)",
            (entity_id, name, latitude, longitude),
        )
        cursor.execute(
            "INSERT INTO discovery_source_records "
            "(source_id, external_id, entity_id, raw_payload, fetched_at) "
            "VALUES (?, ?, ?, '{}', ?)",
            (SFA_SOURCE_ID, entity_id, entity_id, now),
        )
        cursor.execute(
            "INSERT INTO discovery_food_profiles "
            "(entity_id, venue_kind, currency, dietary_attributes, source_id) "
            "VALUES (?, ?, 'SGD', '[]', ?)",
            (entity_id, kind, SFA_SOURCE_ID),
        )
        cursor.execute(
            "INSERT INTO discovery_food_safety_profiles "
            "(entity_id, licence_number, safe_grade, business_type, source_id, observed_at) "
            "VALUES (?, ?, 'A', 'Food business', ?, ?)",
            (entity_id, entity_id, SFA_SOURCE_ID, now),
        )
    conn.commit()
    conn.close()


def test_database_food_provider_returns_only_nearby_venues(food_database):
    venues = DatabaseFoodProvider(limit=8, max_distance_km=3).discover(
        latitude=1.3,
        longitude=103.8,
    )

    assert [venue.name for venue in venues] == ["Nearby Noodles"]
    assert venues[0].distance_km < 0.1
    assert venues[0].safe_grade == "A"


def test_food_skill_exposes_evidence_and_travel_guidance():
    provider = FakeFoodProvider(
        [
            FoodVenue(
                id="food:1",
                name="Licensed Restaurant",
                venue_kind="restaurant",
                address="1 Example Street Singapore 123456",
                postal_code="123456",
                latitude=1.31,
                longitude=103.81,
                safe_grade="B",
                business_type="Restaurant",
                distance_km=1.6,
            )
        ]
    )
    context = UserContext(
        intent="Find a restaurant near me under $20 that is open now",
        current_place=Place(name="Here", latitude=1.3, longitude=103.8),
    )

    result = SgFoodSkill(provider).execute(
        context, {"budget_sgd": 20, "open_now": True}
    )

    assert result.success is True
    assert provider.calls[0]["venue_kinds"] == ("restaurant",)
    assert result.data["places"][0]["safe_grade_evidence"] == (
        "Singapore Food Agency"
    )
    assert result.data["places"][0]["taste_evidence"] == "unknown"
    assert result.data["places"][0]["travel_guidance"] == (
        "consider public transport or a short ride"
    )
    assert "not taste or popularity" in result.summary
    assert "cannot yet verify which results are open now" in result.summary
    assert result.actions[0].metadata["capability"] == "food"
    assert result.summary.startswith("I found these licensed food options nearby")
    assert "Licensed Restaurant (" not in result.summary


def test_food_skill_requires_location_when_no_search_results():
    result = SgFoodSkill(FakeFoodProvider([])).execute(
        UserContext(intent="Recommend food"), {}
    )

    assert result.success is False
    assert "Where are you starting from?" in result.summary


def test_food_skill_preserves_legacy_beta_fallback():
    result = SgFoodSkill(FakeFoodProvider([])).execute(
        UserContext(
            intent="What should I eat at Maxwell Food Centre?",
            current_place=Place(name="Maxwell Food Centre"),
        ),
        {"location": "Maxwell Food Centre"},
    )

    assert result.success is True
    assert any(item["name"] == "Tian Tian Chicken Rice" for item in result.data["places"])
    assert result.data["evidence_scope"]["legacy_beta_fallback"] is True


def test_food_skill_does_not_infer_cafes_from_restaurant_licences():
    provider = FakeFoodProvider([])
    result = SgFoodSkill(provider).execute(
        UserContext(
            intent="Find a cafe near me",
            current_place=Place(name="Here", latitude=1.3, longitude=103.8),
        ),
        {},
    )

    assert result.success is False
    assert "Cafés are a bit tricky" in result.summary
    assert provider.calls == []


def test_food_provider_validates_query_bounds():
    with pytest.raises(ValueError, match="limit"):
        DatabaseFoodProvider(limit=26)
    with pytest.raises(ValueError, match="max_distance"):
        DatabaseFoodProvider(max_distance_km=21)
    with pytest.raises(ValueError, match="pool limit"):
        DatabaseFoodProvider().discover_pool(
            latitude=1.3, longitude=103.8, limit=501
        )


def test_shortlist_feature_flag_caps_and_explains_live_food_results(
    food_database, monkeypatch
):
    monkeypatch.setenv("FOOD_RANKING_MODE", "shortlist")
    result = SgFoodSkill(
        DatabaseFoodProvider(limit=8, max_distance_km=3)
    ).execute(
        UserContext(
            intent="Find lunch near me",
            current_place=Place(name="Here", latitude=1.3, longitude=103.8),
        ),
        {},
    )

    assert result.success is True
    assert result.data["ranking_mode"] == "shortlist"
    assert result.data["ranking_mode_requested"] == "shortlist"
    assert len(result.data["places"]) <= 3
    assert result.data["places"][0]["recommendation_role"] == "closest_suitable"
    assert result.actions[0].metadata["ranking_mode"] == "shortlist"
    assert result.summary.startswith("Can — here are a few licensed food options nearby")
    assert "My closest suitable pick is" in result.summary


def test_invalid_food_ranking_mode_fails_closed_to_legacy(monkeypatch):
    monkeypatch.setenv("FOOD_RANKING_MODE", "experimental")

    assert configured_food_ranking_mode() == "legacy"
