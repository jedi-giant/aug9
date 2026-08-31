# Aug9 beta failure-review playbook

## Triage rhythm

Review feedback every two days during the structured beta. Group failures by capability, card, reason code, journey step and software version. Review repeated patterns rather than isolated preferences.

## Severity

- **P0:** privacy leak, authentication bypass or dangerous advice. Stop the beta and fix immediately.
- **P1:** broken primary journey, cross-session context, empty result or consistently incorrect recommendation. Fix before adding testers.
- **P2:** stale, too-far or weakly relevant recommendation. Batch into the next ranking/data release.
- **P3:** wording, visual polish or individual preference. Track and address when repeated.

## Decision rules

1. Reproduce each P0/P1 with the exact journey and session boundary.
2. Identify whether the failure belongs to intent/planning, context, provider, data quality, ranking, rendering or analytics.
3. Add an automated regression test before fixing a reproducible defect.
4. Deploy behind the existing API contract, run the production smoke, and retest the original journey.
5. Record the resolution and compare the same metric in the next cohort.

Broader launch proceeds only when the structured-beta launch gates remain satisfied and no open P0/P1 issue remains.
