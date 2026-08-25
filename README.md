# Aug9 🇸🇬

Aug9 is an open-source Singapore personal agent that turns trusted local data
into useful everyday answers and actions.

## Current capabilities

- `sg_place`: resolve Singapore places through OneMap
- `sg_weather`: retrieve location-aware forecasts from data.gov.sg
- `sg_transport`: generate walking routes
- `sg_hawkers`: discover curated hawker centres
- Food recommendations through the legacy compatibility handler
- Optional structured actions for directions and place links

The public API keeps a stable text response while exposing richer clients to
optional actions and skill metadata.

## Architecture

```text
User → Planner → SkillRegistry → Skill → Provider → trusted data source
                         ↓
                  response + actions
```

The planner requests capabilities such as `place_resolution`. The registry
selects a skill such as `sg_place`, and the skill calls a provider such as
OneMap. This separation lets contributors add or replace providers without
coupling them to the planner.

## Local setup

Requirements:

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

Install dependencies:

```bash
uv sync
```

Copy the environment template and add your own credentials:

```bash
cp .env.example .env
```

Never commit `.env` or paste credentials into an issue or pull request.

Run the API:

```bash
uv run uvicorn aug9.api.main:app --reload
```

Send a request:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "local-user",
    "session_id": "local-session",
    "message": "Show me hawker centres near Newton"
  }'
```

## Tests

Run tests that do not call external services:

```bash
uv run pytest -m "not integration"
```

Tests that contact live providers or language models must use the
`integration` marker and are intentionally excluded from the default command.

## Build a skill

Start with [the skill-development guide](docs/skill-development.md) and copy
the files in [`skills/_template`](skills/_template). A production skill needs
a provider boundary, registry wiring, deterministic unit tests, and user-facing
instructions.

Discovery-data contributors must also follow the
[source and licensing policy](docs/discovery-data-governance.md).

## API compatibility

`POST /chat` accepts `user_id`, `session_id`, `message`, and an optional
client-generated `task_id`. Its response is:

```json
{
  "response": "Human-readable answer",
  "actions": [],
  "metadata": {}
}
```

Clients may rely on `response`. `actions` and `metadata` are additive and may
be empty.

`metadata.task_id` links the generated result to subsequent product events.
Clients can send bounded, prompt-free activation events to `POST /events` for
action clicks, feedback, sharing, and explicit task completion. Product-event
analytics deliberately do not accept raw prompt or free-text fields. See the
[product requirements](docs/product-requirements.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Keep credentials and personal data out
of commits.

## License

Licensed under the terms in [LICENSE](LICENSE). Third-party notices are in
[NOTICE](NOTICE).
