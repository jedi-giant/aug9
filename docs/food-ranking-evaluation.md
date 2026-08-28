# Food ranking evaluation

Aug9 evaluates food-ranking changes offline before they can affect `sg_food`.
The initial policy is a deterministic regression harness, not a claim that the
five cases represent all Singapore food preferences.

The policy weights are:

- distance: 40%;
- expressed request relevance: 25%;
- active organic editorial food-quality evidence: 15%;
- source and entity-match provenance: 10%;
- evidence freshness: 10%.

Distance remains the largest factor so an award cannot turn an impractically
distant venue into the default nearby recommendation. Editorial evidence can
break a reasonable tie, while a clearly relevant result can beat generic media
coverage. Each result exposes every factor, score, weight and explanation.

SFA SAFE grades are excluded because they describe regulatory food-safety track
records rather than taste. Sponsored and merchant-submitted evidence is excluded
from the editorial signal. Google ratings are excluded while the rating gate is
in shadow mode. Missing ratings never create a penalty.

Run the versioned evaluation set with:

```bash
uv run aug9-evaluate-food-ranking
```

The command exits unsuccessfully if any expected ordering regresses. The report
also states `live_ranking_affected: false`; passing this checkpoint does not
enable the policy. Before live integration, expand the set with reviewed real
queries, compare the candidate orders against current distance ranking, and
approve the explanations shown to users.

## Production-data shadow comparison

After the synthetic regression set passes, compare real nearby SFA candidates
without changing live order:

```bash
uv run aug9-report-food-ranking-shadow \
  --latitude 1.2803 --longitude 103.8448 --pool-limit 250 --limit 12 \
  --intent "Find lunch near me"
```

The report shows the current distance rank, proposed rank, rank movement,
editorial-record count and every scoring factor. Optional `--venue-kind` values
are `restaurant`, `hawker_stall` and `food_court_stall`. This command is read-only
apart from normal database schema initialisation.

The pool is scored before the display limit is applied. The report separately
states pool size, displayed size, editorial coverage and the largest group of
entities sharing one coordinate. Alphabetical ordering inside a OneMap
food-centre coordinate tie is explicitly not treated as a quality signal.

The shadow report also emits a three-role MVP shortlist:

1. `best_supported` — the strongest nearby candidate with active organic
   editorial food-quality evidence;
2. `closest_suitable` — the closest remaining licensed establishment;
3. `nearby_alternative` — the highest-ranked remaining option at a different
   mapped coordinate.

The selector deduplicates entities and coordinate groups. It may return fewer
than three choices rather than pad the shortlist with indistinguishable stalls.
Five-result expansion remains a future explicit user action; live `sg_food`
continues to use its existing behavior during this shadow checkpoint.

Shortlist relevance is request-aware. Names are conservatively classified as
`meal`, `beverage`, `dessert` or `unknown`; unknown remains eligible without an
invented cuisine claim. A general food or meal request will not use an explicitly
beverage- or dessert-labelled venue for a shortlist role. Explicit coffee, juice,
drink or dessert requests reverse the relevant suitability filter. These name
signals are a fallback until governed dish and cuisine tags have broader coverage.
For the `closest_suitable` role, candidates are grouped into 100-metre distance
tiers. An explicit category match is preferred over `unknown` inside the same
tier; a venue in a farther tier cannot leapfrog a genuinely closer suitable
option merely because its name is more descriptive.

## Feature-flagged live integration

The public `sg_food` skill keeps legacy behavior unless Railway sets:

```text
FOOD_RANKING_MODE=shortlist
```

When enabled for coordinate-based food requests, Aug9 evaluates a 250-candidate
pool and returns at most three role-diversified choices. The existing chat API
shape, legacy location fallback, action links and evidence disclosures remain
compatible. Database failures in the shortlist evidence path fall back to legacy
ranking. Missing or unrecognised flag values also resolve to `legacy`.

Skill metadata, direction-action metadata and product result events record the
effective ranking mode. `aug9-report-product-analytics --days 7` groups result
generation by `ranking_modes`. Roll back immediately by setting
`FOOD_RANKING_MODE=legacy` and redeploying; no data migration reversal is needed.

The same report joins result, action, completion and feedback events by stable
task ID. `ranking_mode_outcomes` separates result-task counts, action-click rate,
successful-task rate and positive-feedback rate for each effective mode. This
lets the rollout be evaluated without requiring Base44 to submit a new field.
