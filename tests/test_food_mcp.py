from aug9.mcp_server import get_sg_food


def test_mcp_food_returns_recommendations():

    result = get_sg_food(
        "Maxwell Food Centre"
    )

    assert result["status"] == "success"
    assert len(result["recommendations"]) > 0
