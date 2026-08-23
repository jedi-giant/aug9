from aug9.core.llm import client


def create_embedding(
    text: str,
) -> list[float]:

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )

    return response.data[0].embedding


def cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:

    dot = sum(
        x * y
        for x, y in zip(a, b)
    )

    magnitude_a = sum(
        x * x
        for x in a
    ) ** 0.5

    magnitude_b = sum(
        y * y
        for y in b
    ) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot / (
        magnitude_a * magnitude_b
    )
