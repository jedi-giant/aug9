# Discovery data governance

Aug9 keeps canonical facts, licensed partner content, editorial links, and
research references separate. A publicly accessible page is not assumed to be
licensed for ingestion.

## Permission classes

| Class | Canonical ingestion | Intended use |
|---|---:|---|
| `open_data` | Yes | Data published under a compatible open licence |
| `licensed_partner` | Yes | Fields permitted by a written agreement |
| `link_only` | No | Attribution and outbound links only |
| `research_only` | No | Source discovery and independent verification |
| `prohibited` | No | Do not use |

The discovery repository enforces this boundary: only `open_data` and
`licensed_partner` sources can write canonical entities, source records, or
field provenance.

## Initial source register

These classifications are conservative defaults and must be reviewed whenever
terms or partnership status changes.

| Source | Initial class | Notes |
|---|---|---|
| data.gov.sg / NEA hawker centres | `open_data` | Cite the agency and applicable Open Data Licence |
| OneMap | `open_data` | Use according to OneMap terms and attribution requirements |
| STB Tourism Information Hub | `research_only` | Promote to `licensed_partner` after API access and terms review |
| Hotels Licensing Board dataset | `open_data` | Canonical licensed-hotel location layer |
| `kangcodex/singapore-skills` | `research_only` | MIT code may be adapted with attribution; audit every upstream source separately |
| `mayimian123/sg-event` | `research_only` | No repository licence confirmed; use as a source map only |
| Today Do What | `link_only` | Seek a feed or commercial partnership before ingestion |
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
