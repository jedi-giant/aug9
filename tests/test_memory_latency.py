from unittest.mock import patch

from aug9.core.memory_agent import should_extract_memories
from aug9.core.semantic_memory import retrieve_semantic_memories


def test_memory_extraction_is_skipped_for_one_time_request():
    assert should_extract_memories("What is the weather at Maxwell Food Centre?") is False


def test_memory_extraction_runs_for_explicit_preference():
    assert should_extract_memories("I prefer vegetarian food") is True
    assert should_extract_memories("Remember that I live in Tampines") is True


@patch("aug9.core.semantic_memory.create_embedding")
@patch("aug9.core.semantic_memory.get_embeddings", return_value=[])
def test_semantic_retrieval_skips_embedding_without_stored_memories(
    _mock_get_embeddings, mock_create_embedding
):
    assert retrieve_semantic_memories("user", "weather") == []
    mock_create_embedding.assert_not_called()
