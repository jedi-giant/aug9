# Discovery data governance

Aug9 keeps canonical facts, licensed partner content, editorial links, and
research references separate. A publicly accessible page is not assumed to be
licensed for ingestion.

## Permission classes

| Class | Canonical ingestion | Intended use |
|---|---:|---|
| `open_data` | Yes | Data published under a compatible open licence |
| `licensed_partner` | Yes | Fields permitted by a written agreement |
| `legal_reviewed` | Yes | Minimal factual extraction approved by Aug9's counsel; not open data or a partnership |
| `link_only` | No | Attribution and outbound links only |
| `research_only` | No | Source discovery and independent verification |
| `prohibited` | No | Do not use |

The discovery repository enforces this boundary: only `open_data`,
`licensed_partner`, and specifically approved `legal_reviewed` sources can
write canonical entities, source records, or field provenance.

## Initial source register

These classifications are conservative defaults and must be reviewed whenever
terms or partnership status changes.

| Source | Initial class | Notes |
|---|---|---|
| data.gov.sg / NEA hawker centres | `open_data` | Cite the agency and applicable Open Data Licence |
| OneMap | `open_data` | Use according to OneMap terms and attribution requirements |
| STB Tourism Information Hub | `research_only` | Retired on 31 July 2025; do not build a new integration. Ask STB for the current replacement API or data-access channel |
| Hotels Licensing Board dataset | `open_data` | Canonical licensed-hotel location layer |
| `kangcodex/singapore-skills` | `research_only` | MIT code may be adapted with attribution; audit every upstream source separately |
| `mayimian123/sg-event` | `research_only` | No repository licence confirmed; use as a source map only |
| Honeycombers | `link_only` | Written permission is required before reproducing or adapting event content |
| Visit Singapore Events Guide | `link_only` | Hyperlinking is allowed; automated copying requires STB's prior written permission |
| ieatishootipost | `link_only` | Content requires express permission or a licence |
| Miss Tam Chiak | `link_only` | Do not copy articles, reviews, or photography without permission |
| SETHLUI.com | `link_only` | Public terms do not permit commercial reuse of site materials |
| Google Places | `link_only` | Do not use Places content to build the canonical database |

## Field-level requirements

Every imported field must retain:

- source ID
- source record ID
- original external ID
- fetch and verification timestamps
- source URL where applicable
- licence or partner classification

Descriptions, ratings, photographs, editorial labels, prices, opening hours,
and availability must not be inferred to be reusable merely because they are
visible online.

## Commercial separation

Organic recommendation quality and commercial eligibility are separate.
Referral or sponsored actions must identify the partner and carry an explicit
user-facing disclosure. Paying partners do not silently receive higher organic
ranking.

## Official NEA hawker import

The NEA importer uses the official data.gov.sg GeoJSON download flow and is
explicitly invoked; it does not run during API startup or chat requests.

```bash
uv run aug9-import-nea-hawkers
```

Each run registers the source, validates Singapore coordinates, upserts records
idempotently, records field provenance, and stores received/upserted/rejected
counts. Run it first in a non-production database and review the counts before
running it as a Railway one-off job.

## Historical food-establishment statistics

Collection 1447 contains annual national aggregates, not individual places.
Its two datasets are therefore imported into `market_statistics`, never into
`discovery_entities` and never into customer-facing venue search.

```bash
uv run aug9-import-food-statistics
```

The importer stores the source dataset and row identifiers, original payload,
fetch time, metric, category, period, value, unit, and geography. It is
idempotent and records every run in `discovery_ingestion_runs`. The public API
works without credentials for development; production may set
`DATA_GOV_SG_API_KEY` for the higher authenticated rate limit.

## Official HLB hotel import

The Hotels Licensing Board GeoJSON is imported as canonical hotel entities and
hotel profiles. The importer retains official names, source IDs, postal codes,
coordinates, room counts, and source-update timestamps.

```bash
uv run aug9-import-hlb-hotels
```

`KEEPERNAME` is excluded because it can contain personal information.
`HYPERLINK` is also excluded because the published field may contain an email
address rather than a verified public website. Neither field is retained in the
stored raw payload. All hotel records are written in one transaction to keep
production imports idempotent and efficient.

Hotel addresses are enriched separately through OneMap so HLB location facts
and SLA address facts retain independent provenance. The job authenticates
once and processes at most 50 hotels per run by default:

```bash
uv run aug9-enrich-hotel-addresses
```

Set `HOTEL_ADDRESS_ENRICHMENT_LIMIT` between 1 and 100 to change the batch size.
Only exact postal-code matches are accepted. Existing HLB coordinates are not
overwritten, and completed hotels are skipped on subsequent runs.

## Upcoming events

The `sg_events` runtime reads canonical event records from ingestible sources.
Event profiles retain start and end times, category, organiser, ticketing and
price metadata, and the official source or booking URL. Expired records are
excluded by the runtime.

STB TIH cannot be used as the launch feed because STB retired it on 31 July
2025. Historical data.gov.sg arts datasets must not be presented as upcoming
events. Blogs, aggregators, and the referenced event repositories remain
`link_only` or `research_only` unless their classification is explicitly
changed following permission or legal review. When no canonical event matches,
Aug9 may offer clearly attributed outbound links to Honeycombers and Visit
Singapore. Linked pages remain external; their event text, images, ratings,
and compilation are not copied into Aug9's canonical database.

## Data aggregation engine

All new API, approved-web, and moderated-submission adapters should emit the
shared `AggregationRecord` model and pass through `DataAggregationEngine`.
The engine normalises text and postal codes, optionally resolves incomplete
addresses through a OneMap-compatible geocoder, generates deterministic
cross-source entity identifiers, records field provenance, and applies a hard
per-run record cap. Source permission is checked before collection begins, so
`link_only`, `research_only`, and `prohibited` sources cannot enter the
canonical store.

Publisher prose, reviews, photographs, social posts, and inferred sentiment
must not be placed in `raw_facts`. Each adapter is responsible for emitting
only fields allowed by that source's licence, agreement, or recorded legal
review. User submissions require moderation before they are represented by an
ingestible source.

Expired events can be archived with a separate scheduled job:

```bash
uv run aug9-archive-expired-events
```

Run source importers first and the expiry job afterwards. Delivery continues
through the existing discovery repository, skills, API, Base44 interface, and
future Telegram adapter, keeping collection concerns out of public contracts.

Retired integrations, currently Eventbrite and Source 1, are deactivated during
schema initialization. Previously imported entities are archived rather than
deleted so ingestion and provenance audit records remain available.

## Counsel-approved public event collection

The multi-source public event job covers Visit Singapore, Honeycombers,
SETHLUI.com, Miss Tam Chiak, HeritageSG, DanielFoodDiary.com,
ieatishootipost, Eventbrite, Peatix, SISTIC, and Today Do What. Each is
registered separately as `legal_reviewed`; approval for one source never
enables another source implicitly.

```bash
uv run aug9-import-public-events
```

The collector checks each site's robots policy, stays within an explicit HTTPS
host boundary, waits at least three seconds between requests to the same host,
limits pages and response sizes, and continues when one source is unavailable.
Set `PUBLIC_EVENT_MIN_INTERVAL_SECONDS` to a value greater than or equal to 1;
the production recommendation is 3 or higher. Schedule no more than one run per
day initially.

Only schema.org Event objects and the existing factual activity-card format are
accepted. Stored fields are limited to event name, dates, venue/address, postal
code, price, and source/booking URL. Publisher descriptions, article text,
images, reviews, author/performer profiles, email addresses, social handles,
and other personal data are discarded. Aug9 generates its own short factual
description. Pages without usable event structure produce zero records instead
of triggering broad article extraction.

A source blocked by robots or redirected outside its approved host boundary is
recorded as a failed ingestion and skipped. Ticketmaster and Facebook Events
are not configured as collection sources.

The job prints a `starting` line before each source. PostgreSQL connections use
a 10-second connection timeout, 10-second lock timeout, and 60-second statement
timeout by default, preventing an unavailable or locked database from leaving a
cron worker hanging indefinitely. These can be adjusted with
`DATABASE_CONNECT_TIMEOUT_SECONDS`, `DATABASE_LOCK_TIMEOUT_SECONDS`, and
`DATABASE_STATEMENT_TIMEOUT_SECONDS`.
