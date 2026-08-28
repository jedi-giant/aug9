# SFA licensed food establishments

Aug9 imports current consumer-facing food establishments from the Singapore Food
Agency's public Track Records for Licensed Food Establishments service.

The default import makes three sequential requests, spaced two seconds apart:

- Restaurants, including small restaurants and restaurants with catering
- NEA-managed food stalls
- Stalls within coffee shops, canteens and food courts

Run after deployment with:

```bash
uv run aug9-import-sfa-food-establishments
```

The importer stores business name, establishment address, postal code, licence
number, business type and the currently observed SAFE grade. It deliberately does
not retain `licenseeName`, and records whose business name is missing or `NA` are
rejected rather than substituting a potentially personal licensee name.

SAFE grades are regulatory evidence, not restaurant reviews. They must not be
presented as measures of taste or popularity. The SFA record establishes that a
named business was licensed when observed; cuisine, dishes, prices, opening hours,
coordinates and recommendation suitability require separate evidence.

Each successful run is treated as a complete snapshot for the configured business
types. Previously imported records missing from a later snapshot are archived so a
closed or no-longer-returned licence cannot remain available indefinitely.

Source attribution:

> Contains information from SFA Licensed Food Establishments accessed from the
> Singapore Food Agency, made available under the Singapore Open Data Licence 1.0.

The former NEA list ending in September 2016 is not imported as current availability
evidence. It may later be used in a quarantined matching process, but must never
reactivate or recommend an establishment without current confirmation.

## OneMap enrichment

After importing SFA records, enrich a bounded batch with:

```bash
uv run aug9-enrich-food-locations
```

The default batch contains at most 250 records. Records sharing a postal code share
one OneMap lookup within the run, and unique external requests are spaced by 0.2
seconds. Successful matches store coordinates with OneMap provenance. Rejections
are recorded and skipped by subsequent runs so the command is safely resumable.

Configure the batch with `FOOD_LOCATION_ENRICHMENT_LIMIT` (maximum 500) and the
delay with `FOOD_LOCATION_REQUEST_DELAY_SECONDS`. Run repeatedly until the command
reports `received=0`.

For a large catalog, process multiple bounded batches in one resumable invocation:

```bash
FOOD_LOCATION_ENRICHMENT_LIMIT=500 uv run aug9-enrich-food-locations --max-batches 40
```

The command authenticates with OneMap once, prints progress after every committed
batch, and stops early when the catalog is complete. `--max-batches` is capped at
100 so every invocation retains a finite work limit. If Railway interrupts the
command, rerunning it continues with the first unattempted record.

Review catalog coverage before exposing the records to recommendations:

```bash
uv run aug9-report-food-catalog
```

This reports active SFA establishments by venue kind and SAFE grade, missing
postal codes and coordinates, and the number of successful and rejected OneMap
enrichment attempts.
