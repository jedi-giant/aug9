# Contributing to Aug9

Thank you for helping build an open Singapore personal-agent ecosystem.

## Development setup

1. Fork and clone the repository.
2. Install Python 3.12 or newer and `uv`.
3. Install dependencies with `uv sync`.
4. Copy `.env.example` to `.env` and add only the credentials needed locally.
5. Run `uv run pytest -m "not integration"` before making changes.

Never commit credentials, `.env`, production user data, or provider responses
that contain personal information.

## Adding a skill

Read [docs/skill-development.md](docs/skill-development.md) and begin with
[`skills/_template`](skills/_template). Keep this boundary:

```text
planner capability → registered skill → provider → external data source
```

A new production capability should include:

- a narrowly named planner capability
- an `Aug9Skill` implementation
- a provider interface that isolates network or data access
- registration in `core/default_skills.py`
- planner routing and execution ordering where required
- deterministic unit tests with provider fakes
- an integration test marker for any live-network test
- a user-facing `SKILL.md`
- documentation for new environment variables

Do not put provider credentials or HTTP calls directly in the planner,
executor, or frontend.

## Compatibility

- Preserve existing planner capabilities unless a migration is documented.
- Keep the public `response` field stable.
- Add frontend features through optional `actions` or `metadata` when possible.
- Do not change food or weather behavior as a side effect of another skill.

## Pull requests

Keep pull requests focused and include:

- the user problem and chosen approach
- affected capabilities and providers
- tests added or updated
- the non-integration test result
- API compatibility impact
- deployment or environment changes
- screenshots for user-interface changes

Use the pull-request template and do not merge a feature until its local tests,
API contract, and relevant deployment smoke test pass.
