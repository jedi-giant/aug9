# Food candidate staging

Use the staging importer for community or research datasets that are useful for
discovery but do not yet have sufficient freshness, provenance, or field-level
verification for live recommendations.

The staging table is deliberately separate from canonical discovery entities
and food profiles. Staged candidates are never returned by Aug9 Skills.

The importer retains only:

- name
- Singapore coordinates
- factual address text
- factual opening-hours text
- dish tags
- source attribution and status

It does not retain contributor names, personal stories, narrative descriptions,
social-sharing links, icons, or media. Likely permanent closures are
quarantined, invalid records are rejected, and repeated identities are reported
as duplicates.

```bash
uv run aug9-stage-food-candidates \
  --file /app/imports/community-food.geojson \
  --source-id community_food_seed \
  --source-name "Community Food Seed" \
  --permission research_only \
  --attribution "Community food contributors"
```

Promotion into `discovery_food_profiles` requires a separate verification step
and an ingestable source permission (`open_data`, `licensed_partner`, or
`legal_reviewed`).
