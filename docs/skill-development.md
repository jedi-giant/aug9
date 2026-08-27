# Developing an Aug9 skill

An Aug9 skill owns one user-facing Singapore capability while keeping external
data access behind a provider boundary.

## 1. Choose a capability

Capabilities describe what the planner needs, not which vendor supplies it.
Prefer `events` or `parking` over names such as `vendor_events_api`.

Start from a roadmap journey or observed failed task. Document which journeys
the capability enables and why it should be reusable across them. Do not create
a separate Skill when an existing Skill can be extended without losing a clear,
bounded responsibility.

## 2. Create the package

Use this structure:

```text
src/aug9/sg_example/
├── __init__.py
├── provider.py
└── skill.py
tests/test_sg_example.py
skills/sg-example/SKILL.md
```

`provider.py` defines the interface and provider-specific implementation.
`skill.py` translates planner entities and user context into a `SkillResult`.

## 3. Implement the contract

Subclass `Aug9Skill` and define `name`, `description`, `capabilities`, and
`execute`. Successful results should provide a concise `summary`; structured
data belongs in `data`, and safe user actions belong in `actions`.

Return `success=False` for expected no-result or provider-failure states. Do
not fabricate provider data.

## 4. Register and route

Register the skill in `core/default_skills.py`. If the capability is new, add
planner detection and place it in the executor's dependency-aware execution
order. Preserve existing capability names when replacing a legacy handler.

## 5. Test without the network

Inject a fake provider and cover:

- capability matching
- successful structured output
- no-result behavior
- provider failure behavior
- action construction, if present
- compatibility with related capabilities

Mark tests that intentionally call a live service with `@pytest.mark.integration`.

## 6. Document and verify

Complete the skill's `SKILL.md`, document any environment variables in
`.env.example`, and run:

```bash
uv run pytest -m "not integration"
```

For API-visible changes, add a contract test and verify the deployed `/chat`
endpoint before updating a frontend client.

The `SKILL.md` is part of the runtime capability, not only contributor
documentation. It should give the LLM bounded Singapore-specific context,
terminology, capability guidance, examples, limitations, source and freshness
rules, and safe action semantics. It must not encourage the model to invent
missing provider facts.

## 7. Prove journey value

A Skill contribution should include:

- at least one mapped product journey
- a direct Skill evaluation
- an orchestration evaluation with the related Skills used by that journey
- expected capability outcome and action types
- no-result, stale-data, and provider-failure behaviour
- source permission, provenance, privacy, and safety notes

Acceptance is based on bounded behaviour, reusable capability value, and a
measurable improvement to a Singapore life task. Successful invocation alone
is not sufficient.
