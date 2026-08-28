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

Every roadmap item must also identify the meaningful Singapore life task it
completes, the action offered to the user, and the product event that proves
completion. Skills are reusable building blocks, not the unit of product value.

## Dual roadmap model

Aug9 is **journey-led and Skill-built**:

- The product roadmap is prioritised by end-to-end use cases and user outcomes.
- The engineering backlog is implemented through reusable Aug9 Skills,
  providers, shared context, orchestration, and actions.
- Each journey milestone names the Skills it composes and the shared Skill
  improvements it requires.
- Each Skill documents which journeys it enables and is evaluated both alone
  and as part of those journeys.
- Contributors extend Aug9 by adding or improving governed Skills, not by
  creating disconnected agents for every use case.

This preserves a coherent product experience while keeping the architecture
open and extensible. Journey analytics decide what to prioritise; the Skill
registry and contributor framework decide how it is delivered.

---

# First-Chat Roadmap Alignment — August 2026

## Current checkpoint

Aug9 already has most of the technical foundation required for the proposed
launch journeys:

- ✅ Registered Skills and provider separation
- ✅ OneMap place resolution and location caching
- ✅ NEA weather context
- ✅ Hawker, events, hotels, government services, and transport discovery
- ✅ Daily event ingestion, provenance, expiry, enrichment, and quality reports
- ✅ Day and weekend orchestration with walking-distance guardrails
- ✅ Action links, task analytics, latency instrumentation, and signed anonymous
  visitor identity
- ✅ Public API hardening, CORS controls, and endpoint abuse protection

The remaining gap is not another broad content category. It is converting the
existing capabilities into consistently ranked, constraint-aware,
location-first journeys that end in an action.

## Public-beta launch journeys

1. **Nearby food** — prove location → local context → ranked choice → action.
2. **Daily route and errands** — prove feasible multi-stop planning.
3. **Weekend family itinerary** — prove cross-Skill personalisation and weather
   alternatives.
4. **Healthcare and essential-service finder** — prove trusted, current factual
   discovery without diagnosis.
5. **Restaurant and social planning** — prove group constraints and commercial
   action readiness.

The broader first-chat demand map remains discovery input. Travel, commerce,
housing, finance, trends, news, fitness, vouchers, meal planning, pet care, and
wellness should not become separate MVP workstreams until the reusable launch
layers are proven.

---

# v0.3.1 — Location Context and Nearby Food — In progress

This is the next recommended milestone because it improves all five launch
journeys and provides the clearest registration-free first-value experience.

Composed Skills: `sg-place`, `sg-food`, `sg-weather`, and `sg-transport`, with
shared context passed through the planner and executor. New location and ranking
work should strengthen these reusable Skills rather than live only inside a
nearby-food endpoint.

## Location foundation

- Browser geolocation with explicit permission and a manual-location fallback
- Coordinates-to-place reverse geocoding through OneMap
- Coarse neighbourhood and planning-area context
- Short-lived location caching without product-analytics storage of precise
  coordinates
- Clear handling for denied, unavailable, stale, and non-Singapore locations

## Nearby food outcome

Support a first-class request such as:

> "Find the top five lunch options near me under $15."

The result must combine distance, stated budget and preferences, current-time
context, available opening information, weather-aware travel advice, source
provenance, and directions. Missing opening hours or price evidence must be
shown as unknown rather than inferred.

## Completion checkpoint

- Base44 supplies consented coordinates or a manually selected place
- Aug9 resolves a Singapore neighbourhood and ranks nearby candidates
- At least one useful directions/contact/reservation action is returned
- Location-denied and low-data paths remain useful
- First-query, result, action-click, helpfulness, and failure-stage analytics
  are visible in the product report

---

# v0.3.2 — Constraint and Recommendation Engine — Current

Build one shared recommendation pipeline for food, activities, healthcare, and
services:

```text
intent + location + time + party + budget + preferences
  -> hard eligibility filters
  -> distance/travel-time and relevance scoring
  -> provenance/freshness confidence
  -> ranked recommendation with trade-offs
```

Progress:

- ✅ Shared domain-neutral constraint schema
- ✅ Deterministic filtering with separate excluded and insufficient-evidence paths
- ✅ Explainable ranking factors and high/medium/low confidence labels
- ✅ First integration into verified food recommendations
- Missing-constraint prompts
- Opening-hours normalisation and "open now" semantics
- Outcome analytics by failure stage
- A shared Skill contract for constraints, ranking evidence, confidence, and
  actions

---

# v0.4.1 — Multi-stop Daily Planning

- Multiple origin, stop, deadline, and duration constraints
- Walking, public transport, taxi/private hire, and driving choices
- Feasible schedule generation with travel-time buffers
- Parking context where governed data is available
- Re-planning when weather, time, or a stop changes

# v0.4.2 — Family and Social Planning

- Adults/children, age suitability, indoor/outdoor, budget, and accessibility
  constraints
- Convenient meeting-area calculation from multiple starting locations
- Combined activity, event, food, weather, and transport recommendations
- Booking and reservation links with disclosed source/commercial status

# v0.4.3 — Healthcare and Essential Services

- Governed clinic and service-provider profiles
- "Open now" and proximity filtering using verified source fields
- Official/contact/directions actions and freshness notices
- Strict factual-navigation boundary; no diagnosis or personalised medical
  advice

# v0.5 — Action and Monetisation Layer

- Reservation and appointment deep links
- Calendar and reminder actions
- Disclosed affiliate and merchant-referral attribution
- Organic ranking separated from commercial availability
- Revenue per commercial-intent session alongside successful-task metrics

---

# Capability Delivery History

The sections below retain the implementation history of the individual Aug9
Skills. Future prioritisation is governed by the launch journeys above.

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

# v0.3.3 — Community Food Knowledge — Started

- [x] Administrator-only moderated food submission workflow
- [x] Field proposals, evidence records and moderation audit trail
- [x] Fail-closed server-to-server administrator authentication
- [x] Canonical merge with hawker-centre validation and duplicate protection
- [ ] Base44 administrator review interface
- [ ] Public signed-user suggestions with abuse controls
- [ ] Merchant claims and verification
- [ ] Community contributor reputation
- [x] Google Places-assisted matching and non-persistent rating shadow gate
- [ ] Review shadow-gate results and approve multi-observation live policy

# v0.3.4 — Food Discovery v1 — Started

- [x] Current SFA restaurant and stall directory importer
- [x] SAFE-grade provenance separated from recommendation quality
- [x] Personal licensee names excluded from ingestion
- [x] Resumable, postal-code-deduplicated OneMap enrichment for SFA venues
- [x] Add planner-compatible `sg_food` while retaining explicit `sg_hawkers`
- [x] Restaurant and food-court venue-type constraints from SFA evidence
- [x] Typed, source-attributed food recommendation evidence model
- [ ] Evidence ingestion adapters and source-specific policies
- [x] Reviewed Michelin Bib Gourmand pilot evidence importer
- [x] Offline ranking evaluation set and explainable scoring policy
- [x] Production-data food ranking shadow comparison
- [x] Three-role diversified food shortlist in shadow mode
- [x] Query-aware meal, beverage and dessert shortlist suitability
- [x] Integrate evaluated food scoring behind a disabled-by-default feature flag
- [ ] Enable shortlist mode and review latency, actions and user outcomes
- [x] Attribute action and feedback outcomes to ranking mode by stable task ID
- [ ] Availability and opening-hours evidence
- [ ] Food recommendation outcome analytics


---

# v0.3 — Singapore Discovery

## GTM Activation & Learning — In progress

North star:

`Weekly Singapore Tasks Successfully Completed`

Planned before further capability expansion:

- Anonymous acquisition and task-event tracking
- Stable task IDs across result, action, and feedback events
- Action-click and explicit helpfulness completion signals
- Landing-to-first-query and seven-day retention measurement
- Founder-led weekly build-in-public reporting
- Registration-free first value
- Private aggregate activation scorecard

## Food Intelligence ✅

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

Runtime foundation: ✅

- Governed event profiles and provider separation
- Date, category, and location filtering
- Planner, registry, executor, response, and action integration
- Source and booking links with provenance boundaries

Launch-data feed: ✅ Governed public event aggregation with daily refresh,
expiry handling, provenance, and quality reporting

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

Runtime foundation: ✅

- Registered `sg-services` skill with provider separation
- Deterministic routing for common government-service requests
- Curated official government links only
- LifeSG fallback and current-requirements notice

Next:

- Expanded official service coverage and topic taxonomy ✅
- Automated official-link health report ✅
- Service-task outcomes and failed-intent analytics ✅

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

Runtime foundation: ✅

- Registered `sg-planner` orchestration skill
- Day and weekend intent recognition
- Coordinated events, food, and weather execution
- Location-aware follow-up when a starting area is missing
- Automatic walking route from the starting area to the first event ✅
- Distance-aware walking guardrail with transit and taxi alternatives ✅
- Daily OneMap event venue enrichment and proximity ranking ✅
- Native OneMap multimodal routing with resilient fallback ✅

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

Contributor Skills must use the common registry, typed result and action model,
provider-separation pattern, source-governance policy, tests, examples, and
evaluations. Acceptance should be based on bounded behaviour and demonstrated
journey value, not only whether an LLM can invoke the Skill.
