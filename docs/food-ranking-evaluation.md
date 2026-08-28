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
