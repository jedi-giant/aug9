from aug9.core.context import UserContext
from aug9.core.executor import ExecutionResult
from aug9.core.planner import Plan, create_plan
from aug9.core.responder import compose_response
from aug9.core.skill import SkillResult
from aug9.sg_planner import SgPlannerSkill
from aug9.models import FoodRecommendation, FoodResult, SearchStatus
from aug9.core.models import Place


def test_day_plan_requests_coordinate_existing_capabilities():
    plan = create_plan("Plan my Saturday in Singapore")

    assert {"events", "food", "weather", "transport", "lifeops"}.issubset(
        plan.required_capabilities
    )
    assert plan.entities["plan_type"] == "day"


def test_planner_skill_records_when_location_is_missing():
    result = SgPlannerSkill().execute(UserContext(intent="Plan my day"), {})

    assert result.success is True
    assert result.data["location_available"] is False


def test_lifeops_response_combines_outputs_and_requests_starting_area():
    execution = ExecutionResult(
        plan=Plan(intent="Plan my day", required_capabilities=["events", "lifeops"]),
        outputs={
            "events": SkillResult(
                success=True,
                data={"events": [{"name": "Night Festival"}]},
            ),
            "lifeops": SkillResult(
                success=True,
                data={"plan_type": "day", "location_available": False},
            ),
        },
    )

    response = compose_response(execution)

    assert response.startswith("Your Singapore day plan:")
    assert "Night Festival" in response
    assert "starting neighbourhood" in response


def test_planner_skill_builds_structured_itinerary_from_skill_outputs():
    outputs = {
        "food": FoodResult(
            status=SearchStatus.SUCCESS,
            recommendations=[
                FoodRecommendation(
                    name="Chicken rice",
                    description="A local favourite.",
                    place=Place(name="Maxwell Food Centre"),
                )
            ],
        ),
        "events": SkillResult(
            success=True,
            data={
                "events": [
                    {
                        "name": "Garden festival",
                        "starts_at": "2030-08-24T14:00:00+08:00",
                        "address": "Gardens by the Bay",
                        "source_url": "https://example.com/garden-festival",
                    }
                ]
            },
        ),
        "weather": SkillResult(
            success=True,
            data={"weather": {"forecast": "Fair"}},
        ),
        "transport": SkillResult(
            success=True,
            data={"route": {"summary": "Take public transport."}},
        ),
    }

    result = SgPlannerSkill().execute(
        UserContext(current_place=Place(name="Tanjong Pagar")),
        {"plan_type": "day", "_lifeops_outputs": outputs},
    )

    assert [item["type"] for item in result.data["itinerary"]] == [
        "start",
        "food",
        "event",
    ]
    assert result.data["itinerary"][2]["booking_url"] == (
        "https://example.com/garden-festival"
    )
    assert result.data["weather"]["forecast"] == "Fair"
    assert result.data["transport"]["summary"] == "Take public transport."


def test_planner_skill_uses_registered_food_skill_shape_and_route_details():
    outputs = {
        "food": SkillResult(
            success=True,
            data={
                "places": [
                    {
                        "name": "Katong Laksa",
                        "address": "51 East Coast Road",
                        "latitude": 1.305,
                        "longitude": 103.905,
                        "travel_guidance": "walking may be practical",
                        "licensing_evidence": "Singapore Food Agency",
                        "location_evidence": "OneMap",
                        "opening_hours_evidence": "unknown",
                    }
                ]
            },
        ),
        "transport": SkillResult(
            success=True,
            data={
                "recommended_mode": "walk",
                "route": {
                    "summary": "Walk to 51 East Coast Road in about 8 minutes.",
                    "distance_meters": 600,
                    "duration_minutes": 8,
                },
            },
        ),
    }

    result = SgPlannerSkill().execute(
        UserContext(
            current_place=Place(
                name="Katong", latitude=1.304, longitude=103.902
            ),
            intent="Plan a day out in Katong",
        ),
        {"plan_type": "day", "_lifeops_outputs": outputs},
    )

    assert [item["type"] for item in result.data["itinerary"]] == [
        "start",
        "food",
    ]
    assert result.data["itinerary"][1]["title"] == "Katong Laksa"
    assert result.data["itinerary"][1]["provenance"]["location"] == "OneMap"
    assert result.data["travel_legs"][0]["duration_minutes"] == 8


def test_planner_orders_nearby_events_and_builds_consecutive_travel_legs():
    outputs = {
        "events": SkillResult(
            success=True,
            data={
                "events": [
                    {
                        "name": "Far event",
                        "address": "Sentosa",
                        "latitude": 1.2494,
                        "longitude": 103.8303,
                    },
                    {
                        "name": "Near event",
                        "address": "Tanjong Pagar",
                        "latitude": 1.2764,
                        "longitude": 103.8434,
                    },
                ]
            },
        )
    }

    result = SgPlannerSkill().execute(
        UserContext(
            current_place=Place(
                name="Maxwell Food Centre",
                latitude=1.2803,
                longitude=103.8447,
            ),
            intent="Plan my Saturday",
        ),
        {"plan_type": "day", "_lifeops_outputs": outputs},
    )

    itinerary = result.data["itinerary"]
    assert [item["title"] for item in itinerary[1:]] == [
        "Near event",
        "Far event",
    ]
    assert [item["scheduled_for"][11:16] for item in itinerary] == [
        "10:00",
        "14:00",
        "17:00",
    ]
    assert [leg["recommended_mode"] for leg in result.data["travel_legs"]] == [
        "walk",
        "public_transport",
    ]
    assert len(result.actions) == 2
    assert result.actions[1].metadata["leg"] == 2
    assert "travelmode=transit" in result.actions[1].url
