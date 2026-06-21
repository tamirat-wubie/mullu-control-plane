# Governed Work Assistant Dashboard Route Surface

Date: 2026-06-21
Scope: mounted read-only product surface admission note.

## Route

`GET /api/v1/personal-assistant/work-assistant/dashboard/read-model`

This route exposes the fixture-backed operator dashboard projection for **Governed Work Assistant Demo v0**.

## Source chain

- Product naming bridge: `docs/GOVERNED_WORK_ASSISTANT_DEMO_NAMING.md`
- Dashboard contract: `docs/GOVERNED_WORK_ASSISTANT_OPERATOR_DASHBOARD.md`
- Local schema contract: `docs/contracts/governed_work_assistant_operator_dashboard.schema.json`
- Fixture: `examples/governed_work_assistant_operator_dashboard.json`
- Validator: `scripts/validate_governed_work_assistant_operator_dashboard.py`
- Router module: `mcoi/mcoi_runtime/app/routers/work_assistant_dashboard.py`
- Default-app mount: `mcoi/mcoi_runtime/app/routers/pilot.py`
- Route tests: `mcoi/tests/test_work_assistant_dashboard_router.py`

## Behavior

- `GET` returns the governed dashboard projection.
- `POST` is rejected with `405`.
- The response is read-only and fixture-backed.
- The route does not call live connectors.
- The route does not read or mutate mailboxes.
- The route does not send email or calendar events.
- The route does not write repositories.
- The route does not dispatch workers.
- The route does not append live receipts.
- The route does not grant autonomous execution authority.
- The route does not claim production readiness or customer readiness.

## Effect boundary

The route and its underlying dashboard fixture require these fields to remain false:

- `live_connector_execution_allowed`
- `mailbox_read_allowed`
- `mailbox_mutation_allowed`
- `external_send_allowed`
- `calendar_write_allowed`
- `repository_write_allowed`
- `worker_dispatch_allowed`
- `live_receipt_append_allowed`
- `production_readiness_claim_allowed`
- `customer_readiness_claim_allowed`
- `autonomous_execution_authority_allowed`

The route also returns a `route_boundary` object that keeps route-local effect flags false.

## Admission state

Admitted now:

- checked-in dashboard contract
- checked-in fixture
- local schema validation
- standalone router module
- default-app mount
- default-app GET smoke test
- default-app POST rejection test
- no-effect boundary assertions

Not admitted yet:

- SDK client generation surface
- public OpenAPI source spec addition
- live connector observation
- write-capable approval execution
- external send execution
- production/customer readiness claim

## Next safe step

A future PR may add OpenAPI/SDK visibility for this route after SDK generation checks are updated. That PR must remain read-only unless a separate signed approval, identity, scope, expiry, revocation, replay protection, and effect-reconciliation chain is admitted first.
