from aug9.core.planner import create_plan


def test_planner_extracts_location():

    plan = create_plan(
        "What should I eat at Maxwell Food Centre?"
    )

    assert (
        plan.entities["location"]
        == "Maxwell Food Centre"
    )
