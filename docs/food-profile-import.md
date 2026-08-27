# Controlled food-profile import

Use this importer only for open data, licensed partner feeds, or sources that
have completed legal review. Every import requires attribution and retains the
raw source row as provenance.

## CSV contract

Required columns:

- `external_id` — stable identifier from the source
- `name` — stall or food-venue name
- `parent_entity_id` — existing Aug9 venue ID, such as a governed hawker centre

Optional columns:

- `description`, `address`, `postal_code`, `latitude`, `longitude`
- `venue_kind` — defaults to `hawker_stall`
- `price_min`, `price_max`, `currency` — currency defaults to `SGD`
- `dietary_attributes` — pipe-separated verified attributes, such as `halal`
- `cuisine`, `dish` — pipe-separated tags
- `opening_hours_json` — JSON list containing `day_of_week` (Monday is 0),
  `opens_at`, and `closes_at` in 24-hour time
- `reservation_url`, `source_url`, `quality_score`

An example opening-hours value is:

```json
[{"day_of_week": 0, "opens_at": "08:00", "closes_at": "20:00"}]
```

## Railway command

Upload or otherwise make the authorised CSV available to the backend service,
then run:

```bash
uv run aug9-import-food-profiles \
  --file /app/imports/food-profiles.csv \
  --source-id partner_food_2026 \
  --source-name "Authorised Food Partner" \
  --permission licensed_partner \
  --attribution "Authorised Food Partner" \
  --license-name "Partner agreement"
```

The importer rejects records with missing required fields, invalid prices or
hours, unknown parent venues, and unsupported source permissions. Review the
received, upserted, and rejected totals after each run.
