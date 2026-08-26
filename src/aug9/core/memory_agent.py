import re

from aug9.core.llm import client
from aug9.core.memory_schema import MemoryExtractionResult


MEMORY_PATTERNS = (
    r"\bremember\b",
    r"\bdon't forget\b",
    r"\bdo not forget\b",
    r"\bi (?:like|love|prefer|dislike|hate|avoid)\b",
    r"\bi(?:'m| am) (?:allergic|vegetarian|vegan)\b",
    r"\bmy favou?rite\b",
    r"\bi (?:live|stay|work) in\b",
)


def should_extract_memories(user_input: str) -> bool:
    text = user_input.casefold()
    return any(re.search(pattern, text) for pattern in MEMORY_PATTERNS)


def extract_memories(
    user_input: str,
) -> MemoryExtractionResult:

    response = client.responses.parse(
        model="gpt-5.6-luna",
        input=[
            {
                "role": "system",
                "content": """
You are the memory extraction agent for Aug9,
a Singapore personal assistant.

Extract useful user memories.

For each memory determine:

1. category
Examples:
- food
- dislike
- location
- habit
- preference

2. memory_type
Allowed values:
- preference
- dislike
- habit
- temporary_context
- fact

3. confidence
A number between 0 and 1.

4. expires
Set true for temporary information.

Remember:
- "I like chicken rice" = permanent preference
- "I am visiting Japan next week" = temporary_context
- "Find dinner near Maxwell Food Centre" = no memory

Do NOT store:
- temporary requests
- one-time questions
- greetings
- general information

Examples:

User:
"I like chicken rice"

Return:

{
  "memories": [
    {
      "category": "food",
      "value": "chicken rice",
      "memory_type": "preference",
      "confidence": 0.95,
      "expires": false
    }
  ]
}

User:
"I am travelling to Japan next week"

Return:

{
  "memories": [
    {
      "category": "location",
      "value": "Japan",
      "memory_type": "temporary_context",
      "confidence": 0.9,
      "expires": true
    }
  ]
}

User:
"Find dinner near Maxwell Food Centre"

Return:
{
  "memories": []
}
"""
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
        text_format=MemoryExtractionResult,
    )

    return response.output_parsed
