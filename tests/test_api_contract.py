from aug9.api.main import ChatResponse


def test_chat_response_preserves_legacy_response_only_construction():
    result = ChatResponse(response="Hello")

    assert result.response == "Hello"
    assert result.actions == []
    assert result.metadata == {}
