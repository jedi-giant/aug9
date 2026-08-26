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
