# Governed Work Assistant OpenAPI Refresh Handoff

Date: 2026-06-21
Scope: generated OpenAPI source-spec refresh handoff for the mounted dashboard route.

## Route awaiting generated-spec refresh

`GET /api/v1/personal-assistant/work-assistant/dashboard/read-model`

This route is already mounted in the runtime app and covered by public-demo route validation. It is also covered by SDK generation readiness tests that prove `scripts/export_openapi.py` emits the route from the runtime FastAPI app.

## Current admission state

Admitted:

- dashboard contract
- dashboard fixture
- local schema contract
- standalone router module
- default app mount
- public-demo validator coverage
- runtime OpenAPI export readiness coverage

Pending:

- checked-in generated OpenAPI source spec refresh
- generated SDK client visibility
- removal of temporary pending-path allowance in `tests/test_sdk_generation.py`

## Required refresh command

Run from repository root:

```bash
PYTHONPATH=mcoi python scripts/export_openapi.py
```

Expected changed file:

```text
sdk/openapi/mullu.openapi.json
```

## Required cleanup after refresh

After `sdk/openapi/mullu.openapi.json` includes the dashboard route, remove the temporary allowance from `tests/test_sdk_generation.py`:

```python
PENDING_OPENAPI_SOURCE_PATHS = frozenset({WORK_ASSISTANT_DASHBOARD_ROUTE})
```

Then make `test_openapi_source_spec_is_exported_for_sdk_generation` assert that the checked-in spec contains:

```python
assert WORK_ASSISTANT_DASHBOARD_ROUTE in spec["paths"]
```

## Governance boundary

This handoff grants no runtime effect authority. It does not enable:

- connector execution
- mailbox access
- external send
- calendar write
- repository write
- worker dispatch
- live receipt append
- production readiness claim
- customer readiness claim
- autonomous execution authority

## Acceptance criteria for the generated-spec PR

- `sdk/openapi/mullu.openapi.json` includes the dashboard route.
- `tests/test_sdk_generation.py` no longer allows the route to lag as pending.
- Runtime OpenAPI export and checked-in OpenAPI source match again.
- SDK generation dry-run still reports Python and TypeScript generator commands without executing them.
- No generated SDK clients are committed unless the generator toolchain is explicitly available and verified.
