# Governed Work Assistant OpenAPI Refresh Closure

Date: 2026-06-23
Scope: generated OpenAPI source-spec refresh closure for the mounted dashboard route.

## Route

`GET /api/v1/personal-assistant/work-assistant/dashboard/read-model`

This route is mounted in the runtime app, covered by public-demo route validation, and present in the checked-in OpenAPI source. SDK generation readiness tests prove `scripts/export_openapi.py` emits the route from the runtime FastAPI app and that the checked-in OpenAPI source matches the runtime export.

## Admission State

Admitted:

- dashboard contract
- dashboard fixture
- local schema contract
- standalone router module
- default app mount
- public-demo validator coverage
- runtime OpenAPI export readiness coverage
- checked-in OpenAPI source includes the dashboard route
- SDK source-spec visibility covers the dashboard route
- SDK tests contain no pending-path allowance for this route

Pending: none

## Refresh Command

Run from repository root whenever route surfaces change:

```bash
PYTHONPATH=mcoi python scripts/export_openapi.py
```

Expected changed file:

```text
sdk/openapi/mullu.openapi.json
```

## Permanent Test Contract

`tests/test_sdk_generation.py` must continue to assert:

- the checked-in OpenAPI source contains the dashboard route;
- runtime OpenAPI export contains the dashboard route;
- checked-in OpenAPI source and runtime export match for paths and component schemas;
- CLI export writes the dashboard route.

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

## Acceptance Criteria

- `sdk/openapi/mullu.openapi.json` includes the dashboard route.
- `tests/test_sdk_generation.py` has no pending-path allowance for the route.
- Runtime OpenAPI export and checked-in OpenAPI source match again.
- SDK generation dry-run still reports Python and TypeScript generator commands without executing them.
- No generated SDK clients are committed unless the generator toolchain is explicitly available and verified.

## Closure Witness

- PR: `#2140`
- Merge commit: `9b9b8047e971003f64a2c0c00b2d32d3ac24b9d0`
- Linked issue: `#2110`
- Outcome: `SolvedVerified`
