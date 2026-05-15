# SDK/API Stability Review 2026-05-15

Purpose: record the `sdk_api_stability_review` gate for public naming readiness.
Governance scope: public product naming, SDK/API contract stability, generated clients, OpenAPI runtime title, and launch-state boundaries.
Dependencies: `docs/public-naming-readiness.json`, `tests/test_sdk_generation.py`, `docs/46_sdk_generation.md`, `mcoi/mcoi_runtime/app/server_app.py`.
Invariants: technical contract surfaces remain stable unless a versioned compatibility migration is approved; paid public launch remains blocked until all public naming gates close.

## Decision Boundary

Mullu is the public product name. Mullu Platform remains the `platform_term` where existing SDK/API contracts, schema references, OpenAPI metadata, generated client expectations, or integration documentation require a stable technical name.

Do not rename technical contract surfaces solely for public naming cleanup.

## Reviewed Surfaces

| Surface | Current handling | Decision |
| --- | --- | --- |
| OpenAPI runtime title | Uses the existing runtime/platform naming contract | Keep stable |
| `mcoi/mcoi_runtime/app/server_app.py` | Owns application metadata and router composition | Keep stable |
| `tests/test_sdk_generation.py` | Locks SDK generation expectations | Keep stable |
| `docs/46_sdk_generation.md` | Documents generator requirements and packaging constraints | Keep stable |
| `platform_term` | Machine-readable public naming witness field | Keep stable |

## Migration Rule

Any future rename of SDK/API-facing Mullu Platform identifiers requires a versioned compatibility migration with:

1. old and new contract names,
2. deprecation period,
3. generated SDK compatibility tests,
4. schema and OpenAPI fixture updates,
5. release-note evidence,
6. rollback criteria.

## Gate Decision

This review records the technical boundary only. It does not close trademark, domain, legal, homepage, or app-title gates. The paid public launch remains blocked.

STATUS:
  Completeness: 100%
  Invariants verified: [Mullu product name boundary, Mullu Platform technical contract boundary, versioned compatibility migration rule, paid public launch remains blocked]
  Open issues: [official trademark searches, domain ownership evidence, legal review, homepage update, app title update]
  Next action: keep SDK/API contract names stable until a versioned compatibility migration is explicitly approved
