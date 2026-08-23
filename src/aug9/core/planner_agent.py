from aug9.core.llm import client
from aug9.core.llm_planner import LLMPlan
from aug9.core.memory import ConversationState


def create_llm_plan(
    user_input: str,
    memory: ConversationState | None = None,
) -> LLMPlan:

    memory_context = ""

    if memory:
        memory_context = f"""
User memory:

Preferences:
{memory.preferences}

Recent conversation history:
{memory.history[-5:]}
"""

    response = client.responses.parse(
        model="gpt-5.6-luna",
        input=[
            {
                "role": "system",
                "content": """
You are the planning brain of Aug9,
a Singapore personal assistant.

Available capabilities:

- food: recommend food places
- weather: provide weather information

Return a structured plan.

Use:

- food when the user asks about eating, meals, hawker centres, restaurants
- weather when the user asks about rain, forecast, weather

Extract location into entities.location.

For locations:
- Return only the place name.
- Remove words like "near", "around", "at", "from".
- Example:
  "near Maxwell Food Centre"
  should become:
  "Maxwell Food Centre"

Consider the user's memory when creating the plan.
Use memory only as context. Do not invent facts.
"""
            },
            {
                "role": "user",
                "content": f"""
{memory_context}

Current user request:

{user_input}
"""
            },
        ],
        text_format=LLMPlan,
    )

    return response.output_parsed
