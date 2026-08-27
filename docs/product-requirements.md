# Aug9 Product Requirements

## Positioning

Aug9 is **Singapore's open-source personal agent — built for life here.** It
does not compete as a general-purpose search engine or chatbot. It combines
trusted Singapore context, user intent, modular skills, and actionable results
to answer "What should I do?" The long-term brand promise is **Life in
Singapore, figured out.**

## Product model

```text
User intent
  -> location and user context
  -> governed Singapore context layer
  -> relevant Aug9 skills
  -> deterministic logic and AI reasoning
  -> recommendation
  -> action
```

The context layer normalises authoritative, open, licensed-partner, and
moderated community information. The language model sits above that layer and
does not replace it. Source permission and field provenance remain mandatory.

## Initial audience and activation

The initial audience is digitally active Singapore residents making everyday
location, food, weather, transport, activity, and service decisions. The first
value experience must not require registration.

Activation is not account creation. It is:

> A user successfully completes one meaningful Singapore life task.

The initial completion signal is a useful result followed by an action click
or explicit positive feedback. Technical response success alone does not count.

## First-chat demand map

The product demand map includes nearby food, daily route and errand planning,
family itineraries, healthcare and essential-service discovery, restaurant and
social planning, activities, outbound travel, government services, home
services, CDC voucher merchants, housing and finance information, Culture Pass
discovery, new attractions, local trends, fitness, Singapore news, price
comparison, and meal planning.

These are not separate agents or twenty independent roadmap tracks. They are
evidence for a smaller set of reusable capabilities. A new capability should
be prioritised when it helps Aug9 complete several meaningful Singapore life
tasks, not merely answer another category of question.

Health, housing, and personal-finance experiences initially provide factual
navigation, calculators, education, and links to authoritative sources. They
must not present diagnosis, regulated advice, or unsupported eligibility or
availability claims.

## Initial launch journeys

The public-beta experience should prove five end-to-end journeys:

1. **Nearby food:** location, preferences, budget, opening context, ranked
   recommendations, and directions or reservation action.
2. **Daily route and errands:** multiple stops, time constraints, appropriate
   transport modes, weather, and a feasible schedule.
3. **Weekend family itinerary:** party composition, age suitability, indoor
   alternatives, budget, travel time, food, and booking actions.
4. **Healthcare and essential-service finder:** trusted factual listings,
   proximity, opening context, contact details, and directions, without
   diagnosis.
5. **Restaurant and social planning:** group constraints, convenient areas,
   budget, cuisine, travel time, and a reservation action.

The launch scope is complete only when these journeys can move a user from
intent to a useful action. A broad answer without current, relevant options is
not completion.

## Reusable capability model

```text
LOCATION
  browser geolocation -> reverse geocoding -> neighbourhood context
  -> nearby search -> travel-time calculation

DISCOVERY
  food and restaurants -> activities and events -> healthcare
  -> services and merchants -> destinations

CONTEXT
  current time -> weather -> opening hours -> budget -> preferences
  -> transport -> parking -> provenance and freshness

PLANNING
  intent routing -> constraint extraction -> ranking
  -> multi-stop optimisation -> itinerary and schedule generation

ACTION
  directions -> contact -> reservation or appointment
  -> booking -> calendar or reminder -> disclosed commercial referral
```

The layers should remain composable Aug9 Skills with provider separation.
Deterministic filters and scoring handle hard constraints; model reasoning is
used for ambiguity, explanation, and trade-offs. Provider facts, inferred
facts, and generated descriptions remain distinguishable.

## Journey-led product, Skill-led architecture

Aug9 uses two complementary planning views:

- **Product roadmap:** organised around end-to-end user journeys and successful
  Singapore life tasks.
- **Technical architecture:** organised around modular, reusable Aug9 Skills.

A journey is the user-facing promise. A Skill is a governed capability that the
runtime can discover, compose, test, and execute. Product priorities therefore
start with a journey, identify its missing capabilities, and deliver or improve
the smallest reusable Skills needed to complete it.

```text
Journey demand
  -> required capabilities and context
  -> existing and missing Skills
  -> Skill composition through planner and registry
  -> ranked result and action
  -> journey outcome analytics
```

Skills remain important even when they are not displayed as separate roadmap
features. They provide the LLM with bounded Singapore-specific instructions,
capabilities, terminology, provider facts, and action semantics. They also give
external contributors a stable way to extend Aug9 without changing the core
agent or creating another standalone assistant.

Every production Skill should define:

- a unique name, description, and bounded capability set
- Singapore-specific instructions and terminology
- typed inputs, outputs, actions, and failure states
- provider separation, provenance, freshness, and permission boundaries
- deterministic behaviour where practical
- automated tests, examples, and agent evaluations
- privacy and safety constraints
- the journeys it enables and the product outcomes it can emit

The planner may compose several Skills for one journey. A Skill may support
several journeys. Neither the LLM nor a contributor-provided Skill may bypass
source governance, API validation, safety controls, or action disclosure.

### Initial journey-to-Skill composition

| Launch journey | Core Skills | Important additions |
| --- | --- | --- |
| Nearby food | `sg-place`, `sg-food`, `sg-weather`, `sg-transport` | browser location, opening context, ranking |
| Daily route and errands | `sg-place`, `sg-transport`, `sg-planner`, `sg-weather` | multi-stop constraints, feasible scheduling |
| Weekend family itinerary | `sg-events`, `sg-food`, `sg-weather`, `sg-transport`, `sg-planner` | age suitability, indoor fallback, budget |
| Healthcare and essential services | `sg-place`, `sg-services`, `sg-transport` | governed provider profiles, open-now context |
| Restaurant and social planning | `sg-place`, `sg-food`, `sg-transport`, `sg-planner` | group convenience, restaurant data, reservations |

## North star and supporting metrics

The north-star metric is **Weekly Singapore Tasks Successfully Completed**.

Supporting metrics are landing-to-first-query conversion, successful-task
rate, time to first value, weekly and monthly active users, seven-day
retention, tasks per user, action click-through, share and referral rates, and
revenue per commercial-intent session.

Analytics must not store raw prompts in product-event records. Events use an
anonymous visitor ID, session ID, generated task ID, bounded capability and
outcome fields, acquisition campaign fields, and timestamps. Operational logs
and product analytics remain separate.

## Growth loops

- **Build in public:** measure requested and failed tasks, build the
  highest-value capability, and publish the improvement.
- **Sharing:** turn useful itineraries, shortlists, and guides into public
  links that recipients can reuse.
- **Community:** let contributors build modular Singapore skills with clear
  source governance, tests, documentation, and attribution.
- **Local knowledge:** accept moderated, auditable community corrections while
  keeping them separate from authoritative facts.
- **Commercial:** measure disclosed actions and referrals without altering
  organic recommendation quality.

## Monetisation boundaries

Priority order is transaction and affiliate revenue, merchant referrals and
profiles, a hosted Singapore context API, then supplementary advertising.
Sponsored placements must be labelled. Payment must not silently change
organic ranking.

The five launch journeys provide the first commercial hooks: restaurant and
activity reservations, travel and hotel affiliates, qualified home-service
leads, merchant referrals, and disclosed action clicks. Monetisation is added
at the action layer after recommendation quality is measurable. Commercial
availability must not become a hidden ranking advantage.

## Capability and journey analytics

Product events should record the broad intent, capabilities requested,
capability outcomes, constraint completeness, recommendation generation, and
downstream actions. Aggregate reporting should answer:

- Which launch journeys are requested most often?
- Where does a journey fail: location, data coverage, constraints, ranking, or
  action availability?
- Which recommendations lead to directions, contact, booking, or positive
  feedback?
- Which reusable capability would unlock the most currently failed tasks?

Signed anonymous visitor identity protects continuity and event integrity.
Raw prompts, precise user coordinates, and sensitive personal details must not
be copied into product-event records.

## Development principles

1. Singapore context before generic model knowledge.
2. Cache or database before live external calls.
3. Deterministic logic before expensive model calls where practical.
4. Modular skills and provider separation.
5. Intent-to-action instrumentation from the beginning.
6. No mandatory signup before first value.
7. Prioritise work that completes a meaningful Singapore life task.

## Founder-led go-to-market

LinkedIn is the initial acquisition channel. Weekly updates should demonstrate
what Aug9 can now do for someone living in Singapore that it could not do the
week before. Product-event reporting must support credible aggregate stories
about usage, demand, failures, and improvements without exposing personal
prompts.

The Aug9 name comes from the founder's August 9 birthday, Singapore's National
Day. The story should remain authentic and understated: useful local technology,
open development, reduced friction across fragmented services, and public-good
contribution.
