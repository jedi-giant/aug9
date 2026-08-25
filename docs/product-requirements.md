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
