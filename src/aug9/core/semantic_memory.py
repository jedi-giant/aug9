import ast

from aug9.core.database import get_embeddings
from aug9.core.embeddings import create_embedding, cosine_similarity


def retrieve_semantic_memories(
    user_id: str,
    user_input: str,
    limit: int = 3,
):
    stored_rows = get_embeddings(user_id)
    if not stored_rows:
        return []

    query_embedding = create_embedding(user_input)

    scored = []

    for (
        memory_id,
        category,
        value,
        memory_type,
        confidence,
        expires,
        embedding_text,
    ) in stored_rows:

        stored_embedding = ast.literal_eval(embedding_text)

        score = cosine_similarity(
            query_embedding,
            stored_embedding,
        )

        scored.append(
            {
                "memory_id": memory_id,
                "category": category,
                "value": value,
                "memory_type": memory_type,
                "confidence": confidence,
                "expires": bool(expires),
                "semantic_score": score,
            }
        )

    scored.sort(
        key=lambda memory: memory["semantic_score"],
        reverse=True,
    )

    return scored[:limit]
