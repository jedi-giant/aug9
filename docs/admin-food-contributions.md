# Administrator food contributions

Aug9 accepts administrator food records through a moderated submission workflow.
The browser must never call the Railway administrator endpoints directly. A Base44
backend function authenticates the signed-in administrator, then sends the Railway
secret from its server-side environment.

## Railway configuration

Generate a random value containing at least 32 characters and configure it as:

```text
AUG9_ADMIN_API_KEY=<random secret>
```

The same value will later be stored as a Base44 backend secret. It must not be put
in frontend code, browser storage, URLs, analytics or logs.

## Workflow

1. `POST /admin/food-submissions` creates an immutable field proposal in
   `needs_review` status.
2. `GET /admin/food-submissions` lists the review queue.
3. `POST /admin/food-submissions/{id}/approve` validates and atomically merges the
   proposal into the canonical discovery catalogue.
4. `POST /admin/food-submissions/{id}/reject` records a rejection reason.

Every request requires `X-Aug9-Admin-Key`. Missing configuration fails closed with
HTTP 503; missing or incorrect credentials return HTTP 401.

The initial source is `aug9_admin`, classified as `legal_reviewed`. Approved stalls
receive a quality score of 0.7 and become available to the existing hawker Skill
without changing the public chat contract.
