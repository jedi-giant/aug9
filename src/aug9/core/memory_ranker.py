from aug9.core.llm import client
from aug9.core.memory_ranker_schema import MemoryRankingResult


def rank_memories(
    user_input: str,
    memories: list[dict],
) -> MemoryRankingResult:

    response = client.responses.parse(
        model="gpt-5.6-luna",
        input=[
            {
                "role": "system",
                "content": """
You are the memory ranking agent for Aug9,
a Singapore personal assistant.

Your job is to select memories that are useful
for answering the user's current request.

Rules:

- Return only relevant memories.
- Prefer user preferences, dislikes, and habits.
- Ignore unrelated temporary context.
- Score relevance from 0 to 1.
- Explain why each memory is relevant.

Example:

User:
"Find dinner near Maxwell Food Centre"

Memories:
[
 {
  "value": "chicken rice",
  "type": "preference"
 },
 {
  "value": "Japan",
  "type": "temporary_context"
 }
]

Return:

{
 "memories": [
  {
   "value": "chicken rice",
   "relevance_score": 0.95,
   "reason": "Useful for food recommendations"
  }
 ]
}
"""
            },
            {
                "role": "user",
                "content": f"""
User request:

{user_input}

Candidate memories:

{memories}
"""
            },
        ],
        text_format=MemoryRankingResult,
    )

    return response.output_parsed
