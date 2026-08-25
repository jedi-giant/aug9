from aug9.core.planner import create_plan


def test_planner_extracts_location():

    plan = create_plan(
        "What should I eat at Maxwell Food Centre?"
    )

    assert (
        plan.entities["location"]
        == "Maxwell Food Centre"
    )


def test_planner_extracts_transport_endpoints():
    plan = create_plan(
        "How do I get from Maxwell Food Centre to Marina Bay Sands?"
    )

    assert plan.entities["origin"] == "Maxwell Food Centre"
    assert plan.entities["destination"] == "Marina Bay Sands"
    assert "transport" in plan.required_capabilities
