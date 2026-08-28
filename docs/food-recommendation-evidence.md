# Food recommendation evidence

Aug9 stores recommendation evidence separately from the venue catalog and from
the ranking policy. Adding evidence does not automatically change a live rank.

Each evidence record identifies:

- the venue and optional dish it concerns;
- the dimension and specific claim;
- whether the claim is factual, editorial, community or behavioural evidence;
- positive, negative or neutral direction;
- source, source URL, observation time, expiry and confidence;
- organic, sponsored or merchant-submitted commercial status.

The dimensions are food quality, contextual fit, reliability, experience,
regulatory safety, popularity and discovery value. This prevents a service or
queue complaint from being treated as a direct judgment of food quality, and
prevents SFA SAFE grades from being interpreted as taste scores.

Expired evidence is excluded by default. Records are idempotently updated using
the source and its external identifier, and only sources whose permissions allow
ingestion can write evidence. Sponsored and merchant-submitted evidence remains
explicitly labelled so a future organic ranking policy can exclude or cap it.

This schema is the evidence layer only. A later checkpoint will introduce an
auditable candidate-scoring policy after representative evidence and evaluation
queries are available.
