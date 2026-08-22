# Aug9 Roadmap 🇸🇬

Aug9 is building a Singaporean AI Personal Agent.

The goal is to create an AI assistant that understands Singapore context and helps people navigate everyday decisions using trusted local data sources.

---

# Vision

Transform fragmented Singapore information into an intelligent personal operating system.

Examples:

- "Where should I eat?"
- "Should I bring an umbrella?"
- "How do I get there?"
- "What's happening nearby?"
- "Help me plan my day."

---

# Architecture Principles

Every Aug9 capability follows:

1. Define user problem
2. Create Skill instructions
3. Build data integration
4. Expose MCP tool
5. Add automated tests
6. Add agent evaluation

---

# v0.1 — Foundation ✅

Completed:

## Location Intelligence

Capability:

`sg-place-finder`

Powered by:

- OneMap API

Provides:

- Location resolution
- Address
- Postal code
- Coordinates


## Weather Intelligence

Capability:

`sg-weather`

Powered by:

- NEA Weather API

Provides:

- Location-aware weather forecast


## AI Agent Foundation

Built:

- OpenAI Agent
- MCP server
- Skills architecture
- Automated testing

---

# v0.2 — Singapore Daily Assistant ✅ 
✅ Walking route provider integrated
✅ Agent transport evaluation added
✅ Multi-skill agent loading completed

## Transport Intelligence

Capability:

`sg-transport`

Goal:

Help users navigate Singapore.

Examples:

> "How do I get from Maxwell Food Centre to Marina Bay Sands?"

Planned:

- Location-aware routing
- Walking directions
- MRT guidance
- Public transport enrichment

Potential data sources:

- OneMap
- LTA DataMall
- Open routing services


---

# v0.3 — Singapore Discovery

## Food Intelligence

Capability:

`sg-food`

Goal:

Help users discover Singapore food.

Examples:

> "What should I eat at Maxwell Food Centre?"

Planned:

- Hawker centre discovery
- Stall recommendations
- Opening hours
- Cuisine preferences


## Events Intelligence

Capability:

`sg-events`

Goal:

Help users discover Singapore activities.

Examples:

> "What can I do this weekend?"

Planned:

- Events discovery
- Family activities
- Community activities


---

# v0.4 — Singapore Services Assistant

Capability:

`sg-services`

Goal:

Help users navigate Singapore government and essential services.

Examples:

> "How do I renew my passport?"

Planned:

- Government service discovery
- Process guidance
- Official resources


---

# v0.5 — Personal LifeOps

Capability:

`sg-planner`

Goal:

Combine multiple Singapore capabilities into proactive assistance.

Examples:

> "Plan my Saturday morning."

Aug9 combines:

- Weather
- Transport
- Food
- Events
- User preferences


---

# Future Vision

## Aug9 Skill Ecosystem

Community-created skills:

- sg-food-expert
- sg-hdb-helper
- sg-carpark-finder
- sg-parenting-guide
- sg-business-helper

Aug9 becomes a platform where Singapore-specific AI capabilities can be shared and extended.
