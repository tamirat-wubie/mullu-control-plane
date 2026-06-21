# Governed Work Assistant Operator Dashboard Projection

Date: 2026-06-21
Scope: read-only product projection contract only. This document does not create a route, UI, connector call, worker dispatch, repository write, live receipt append, deployment mutation, customer-readiness claim, or production-readiness claim.

## Purpose

This projection gives the operator a simple view of the merged no-effect demo under the operator-facing name:

**Governed Work Assistant Demo v0**

It bridges the existing internal pilot identifier, `governed_team_assistant_pilot_v0`, into a clearer product-facing dashboard name without renaming internal routes, schema keys, fixtures, or identifiers in a breaking way.

## Dashboard panels

The dashboard projection should show:

1. Product name and stage.
2. Assistant readiness.
3. Available skills.
4. Blocked live actions.
5. Draft preview.
6. Approval preview.
7. Dry-run receipt trail.
8. Closure evidence.
9. No-effect boundaries.
10. Next safe implementation steps.

## Required boundaries

The projection must keep all effect fields false:

- live connector execution
- mailbox read or mutation
- external sends
- calendar writes
- repository writes
- worker dispatch
- live receipt append
- production readiness claim
- customer readiness claim
- autonomous execution authority

## Source contracts

The projection is backed by checked-in, no-effect fixtures and contracts:

- `examples/personal_assistant_console_read_model.json`
- `examples/personal_assistant_draft_projection.json`
- `examples/personal_assistant_approval_queue_read_model.json`
- `examples/personal_assistant_receipt_draft_only.json`
- `examples/personal_assistant_readiness_index_receipt.json`
- `docs/GOVERNED_WORK_ASSISTANT_DEMO_NAMING.md`

## Schema and fixture

- Local schema contract: `docs/contracts/governed_work_assistant_operator_dashboard.schema.json`
- Fixture: `examples/governed_work_assistant_operator_dashboard.json`
- Validator: `scripts/validate_governed_work_assistant_operator_dashboard.py`

## Admission rule

This projection is safe to merge only as a read-only contract bundle. A future route or UI must be introduced in a separate PR with its own route tests, no-effect checks, and governance receipt evidence.
