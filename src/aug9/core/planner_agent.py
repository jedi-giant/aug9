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
- transport: provide routes between places
- hawkers: discover Singapore hawker centres
- hotels: discover licensed Singapore hotels
- events: discover upcoming Singapore activities and events
- services: find official Singapore government services
- lifeops: coordinate a multi-capability Singapore day plan

Return a structured plan.

Use:

- food when the user asks about eating, meals, hawker centres, restaurants
- weather when the user asks about rain, forecast, weather
- transport when the user asks how to travel, walk, or get from one place to another
- hawkers when the user asks to find or list hawker centres
- hotels when the user asks to find or list hotels or accommodation
- events when the user asks what to do, or for events, activities, concerts,
  exhibitions, festivals, or weekend plans
- services when the user asks about Singapore passports, Singpass, CPF, tax,
  HDB, work passes, HealthHub, identity cards, birth registration, marriage,
  driving licences, National Service, school registration, starting a business,
  or another government service
- lifeops together with events, food, and weather when the user asks Aug9 to
  plan a day, Saturday, Sunday, weekend, or itinerary

Extract location into entities.location.
Extract a broad event category into entities.category when clearly requested.
For services, copy the request into entities.service_query.
For lifeops, set entities.plan_type to day or weekend.
For transport, extract both entities.origin and entities.destination.

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
