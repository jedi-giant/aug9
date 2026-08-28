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
  --latitude 1.2803 --longitude 103.8448 --pool-limit 250 --limit 12
```

The report shows the current distance rank, proposed rank, rank movement,
editorial-record count and every scoring factor. Optional `--venue-kind` values
are `restaurant`, `hawker_stall` and `food_court_stall`. This command is read-only
apart from normal database schema initialisation.

The pool is scored before the display limit is applied. The report separately
states pool size, displayed size, editorial coverage and the largest group of
entities sharing one coordinate. Alphabetical ordering inside a OneMap
food-centre coordinate tie is explicitly not treated as a quality signal.
