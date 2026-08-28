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

## Michelin Bib Gourmand pilot

The first pilot is a dated 30-entry structured snapshot from the official 2026
Michelin Guide Singapore Bib Gourmand list. It stores only listing identifiers,
names, coordinates, distinction, price band, cuisine label, official URL and
observation time. Descriptions and images are excluded.

Generate review candidates against active SFA establishments with:

```bash
uv run aug9-match-michelin-pilot
```

The matcher uses name and coordinate agreement within a bounded radius and writes
nothing. Even `high_confidence` results require review before conversion into
evidence. Unlisted establishments receive no negative evidence.

The reviewed pilot manifest links 18 of the 30 Michelin listings to active SFA
entities. Import those mappings idempotently with:

```bash
uv run aug9-import-michelin-evidence
```

Each mapping creates one positive, organic `award_or_recognition` record for the
2026 Bib Gourmand distinction with confidence 0.8 and an August 2027 review
deadline. The other 12 Michelin listings remain valid source records but unlinked;
the import fails closed if any approved SFA entity is missing or inactive.

## Google rating shadow gate

Google Places is a volatile, link-only recommendation signal. It never changes
or deletes the canonical SFA establishment record. Aug9 stores only the Google
Place ID and its own match audit data; ratings are retrieved live for a bounded
shadow report and are not persisted.

Set `GOOGLE_PLACES_API_KEY` to a restricted key for Places API (New), then build
links in small, cost-controlled batches:

```bash
uv run aug9-link-google-food-places --limit 50
```

Automatic links require strong name agreement plus either matching postal code
or coordinates within 200 metres. Ambiguous matches and Place IDs already linked
to another SFA entity are rejected. Completed attempts are skipped by later runs
so rejected records do not block progress through the catalog.

Preview the policy without changing live recommendations:

```bash
uv run aug9-report-google-rating-gate --limit 100
```

The report identifies ratings below 2.5 with at least 10 ratings. A venue with
active, organic, positive editorial food-quality evidence is sent to conflict
review rather than shadow suppression. Small samples are labelled insufficient,
and missing ratings are not treated as negative. The report contains Google Maps
attribution links and must remain an operator-only audit until the user-facing
attribution design and a multi-observation activation policy are approved.
