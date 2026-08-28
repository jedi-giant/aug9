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

## Controlled CSV import

Use `aug9-import-food-evidence` only for a licensed or legally reviewed source.
The importer accepts factual and editorial evidence; community and behavioural
signals must enter through their own abuse-controlled pipelines.

Required columns are `external_id`, `entity_id`, `dimension`, `evidence_type`,
`direction`, `claim_key`, `value_json`, `confidence`, `source_url`, `observed_at`,
`commercial_status`; `dish_name` and `expires_at` are optional. Times must include
a timezone and source URLs must use HTTPS.

Only structured JSON is accepted. Free-text descriptions and unknown columns are
rejected, values are capped at 2 KB, and confidence is capped at 0.95 for factual
evidence and 0.85 for editorial evidence. The allowed claims are cuisine, dish
speciality, price, opening hours, queue, service, ambience, accessibility,
consistency, and award or recognition.

Claim-to-dimension rules are enforced. Dish specialities and editorial awards may
support food quality; cuisine and price describe contextual fit; opening hours
describe reliability; ambience and service describe experience. Queue and
consistency evidence may support only their explicitly allowed dimensions. This
prevents operational friction from silently becoming a taste penalty.

After an import, audit coverage with:

```bash
uv run aug9-report-food-evidence
```

The report separates active and expired evidence and groups records by dimension,
evidence type and commercial status. Evidence still remains unavailable to live
ranking until a separately tested scoring policy is enabled.
