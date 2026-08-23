import ast

from aug9.core.database import get_embeddings
from aug9.core.embeddings import (
    create_embedding,
    cosine_similarity,
)


def retrieve_semantic_memories(
    user_input: str,
    limit: int = 3,
):
    query_embedding = create_embedding(
        user_input
    )

    scored_memories = []

    embeddings = get_embeddings()

    for memory_id, embedding_text in embeddings:

        stored_embedding = ast.literal_eval(
            embedding_text
        )

        score = cosine_similarity(
            query_embedding,
            stored_embedding,
        )

        scored_memories.append(
            {
                "memory_id": memory_id,
                "score": score,
            }
        )

    scored_memories.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return scored_memories[:limit]
