# Aug9 Family Discovery Architecture

## Decision

Aug9 will keep one governed discovery catalogue and one skill runtime. Chat,
map browsing, guided journeys and later voice input are presentation and input
surfaces over those shared services; they are not separate recommendation
systems.

## Architecture comparison

| Layer | Original architecture | Target architecture | Change |
|---|---|---|---|
| Sources | Government APIs, licensed/user-provided files and governed public imports | Same sources, plus family-activity providers and community submissions | Extended |
| Ingestion | Source-specific importers normalise into `discovery_entities` and profiles | Same pipeline with a common `activity_profile` for playgrounds, parks, libraries, attractions and indoor play | Extended |
| Governance | Source permission, provenance, ingestion runs and entity quality | Same controls plus field freshness, verification dates and catalogue-gap queues | Extended |
| Spatial | OneMap place resolution and coordinates used inside individual skills | Shared spatial search, map viewport/bounds, distance and neighbourhood filters | Generalised |
| Domain data | Separate food, event, hotel and playground representations | Existing domain profiles remain; family venues share an additive activity profile | Additive, not a migration rewrite |
| Intelligence | Planner selects registered skills; executor returns structured results | Same skill runtime coordinates activity, food, weather and transport into family journeys | Extended |
| Ranking | Capability-specific ranked cards | Shared constraints and evidence, followed by capability-specific ranking policies | Generalised |
| Experience | Chat and recommendation cards | Chat + synchronised map/list/cards + guided journeys; push-to-talk later | New surfaces |
| Actions | Directions, booking/source links and feedback | Same actions plus add-to-plan, compare, save and report inaccurate data | Extended |
| Analytics | Query, result, action and card-feedback events | Same events segmented by surface, filter, journey stage and voice correction | Extended |

## Target flow

```text
APIs / governed imports / community submissions
                    |
                    v
collection -> parsing -> validation -> provenance -> deduplication
                    |
                    v
 discovery_entities + domain profiles + activity_profiles
                    |
          +---------+----------+
          |                    |
          v                    v
 spatial/filter query     registered skills
          |                    |
          +---------+----------+
                    v
       shared ranking and journey state
                    |
          +---------+----------+----------+
          |                    |          |
          v                    v          v
      chat/cards          map/list    guided planner
                                           |
                                      push-to-talk
                                      (later input)
```

## Shared activity profile

The profile stores decision-making attributes that apply across family venues:

- activity kind and indoor/outdoor setting;
- minimum and maximum ages;
- prices, free/paid status and booking requirements;
- typical visit duration;
- water play, structural shelter and natural shade as separate facts;
- features, family facilities and accessibility tags;
- opening-hours summary, source and verification date.

The generic entity remains the canonical identity and spatial record. Events
continue to use event profiles because an occurrence has start/end times;
restaurants continue to use food profiles. A venue may have multiple profiles
without being duplicated.

## Surface responsibilities

- **Chat** interprets intent, remembers refinements and builds a decision or plan.
- **Map** supports spatial exploration and makes clusters/proximity visible.
- **Cards/list** support comparison and expose trustworthy attributes.
- **Guided journeys** collect predictable constraints without requiring a good prompt.
- **Voice** begins as editable push-to-talk transcription and calls the same chat API.

## Delivery sequence

1. Add and backfill the activity profile for the existing playground catalogue.
2. Add a bounded activity-search API with map-safe filters and provenance.
3. Build a synchronised map/list view in Base44 and connect “Ask Aug9 about this”.
4. Add indoor play, parks, libraries and attractions through governed importers.
5. Compose family outing journeys with food, weather and transport.
6. Trial push-to-talk only after text journey accuracy and latency meet beta targets.

## Guardrails

- Never maintain separate chat and map catalogues.
- Do not expose records without coordinates, provenance and active status on the map.
- Do not infer structural shelter from tree shade.
- Treat time-sensitive fields as observations with verification timestamps.
- Keep sponsored or affiliate status explicit and outside organic ranking evidence.
- Do not persist precise browser location beyond the bounded request/session need.
