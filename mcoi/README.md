# MCOI Runtime

Purpose: package the governed swarm work fabric and simple Mullusi platform facade for control-plane integration.

Workspace boundary: this root package is a compact support/runtime surface, not
the canonical Mullusi control-plane platform. Full API server wiring, router
orchestration, nested-mind integration, and release authority live in the
canonical control-plane repository. Do not mirror canonical control-plane files
back into this package unless a governed import plan names the exact module
contract and rollback path.

Governance scope: this package exposes symbolic intelligence workers and plain-language action checks as bounded runtime components. It does not grant universal authority, direct side-effect execution, or memory admission outside governed runtime contracts.

Dependencies: Python 3.12+, setuptools build backend, optional FastAPI gateway adapter.

Invariants:

- Every swarm worker has identity, capability scope, budget scope, and memory scope.
- Every task runs under a finite lease.
- Every inter-agent result is represented as a traceable claim or receipt.
- Side effects require explicit governance decisions before execution authority is granted.
- Closure requires terminal proof.
- Package entry points do not bypass runtime validation.

## Simple User Surface

```powershell
mullu start
mullu start --json
mullu actions
mullu outcomes
mullu workflows
mullu documents
mullu documents --json
mullu workflow docs-update --target docs/README.md
mullu task review-docs --target docs/README.md
mullu task update-docs --target docs/README.md
mullu task notify-support
mullu check --goal "Review docs" --action view --target docs/README.md --allowed-area docs/**
mullu check --goal "Update docs" --action change --target docs/README.md --allowed-area docs/**
mullu check --goal "Notify support" --action send --target support@mullusi.com --allowed-area support@mullusi.com
```

`mullu` is the intended front door for non-technical users. It returns one of three outcomes:

- `Ready`: the action stays inside the allowed area and has required proof.
- `Needs review`: the action has external side effects and requires approval.
- `Blocked`: the action violates scope, proof, or domain constraints.

## Simple App Surface

- `SimplePlatformRuntime` exposes the same outcomes in JSON envelopes.
- `SimplePlatformRuntime.document_manipulation_wiring()` exposes the read-only
  document manipulation component chain for `docs_update` without granting
  execution authority.
- `SimplePlatformRuntime.document_manipulation_wiring_contract()` exposes the
  stable client contract for document manipulation wiring readback.
- `mount_simple_platform_router_from_env(app, env)` mounts the simple routes
  when `MULLU_SIMPLE_PLATFORM_ENABLED=1` and uses
  `MULLU_SIMPLE_PLATFORM_PREFIX` when provided.
- `mount_public_runtime_routes_from_env(app=..., runtime_env=..., clock=...)`
  is the server startup hook that wires the simple platform and read-only
  dashboard routes together behind `MULLU_SIMPLE_PLATFORM_ENABLED` and
  `MULLU_DASHBOARD_ENABLED`; both remain disabled by default.
- `create_simple_platform_fastapi_router(runtime)` mounts stable routes:
  - `GET /api/v1/simple/home`
  - `GET /api/v1/simple/actions`
  - `GET /api/v1/simple/start`
  - `GET /api/v1/simple/documents/wiring`
  - `GET /api/v1/simple/documents/wiring/contract`
  - `POST /api/v1/simple/actions/check`
  - `POST /api/v1/simple/tasks/check`
  - `POST /api/v1/simple/workflows/check`
- `build_operational_dashboard_state(..., simple_action_checks=...)` projects checks into `simple_action_summaries`, `simple_ready_action_refs`, `simple_review_action_refs`, and `simple_blocked_action_refs` for dashboard rendering without granting execution authority.
- `build_operational_dashboard_state(..., simple_workflow_plans=...,
  simple_start_guide=...)` projects simple workflows and the start guide into
  `simple_workflow_summaries`, `simple_start_guide`, and `simple_home_summary`
  for dashboard onboarding without granting execution authority.
- `build_operational_dashboard_state(..., sdlc_validation_receipts=...)`
  projects SDLC validation receipts into `sdlc_receipt_summaries`,
  `sdlc_passed_receipt_refs`, and `sdlc_failed_receipt_refs` for read-only
  software-delivery evidence displays without granting execution authority or
  terminal closure.
- `OperationalDashboardRuntime` and
  `create_operational_dashboard_fastapi_router(runtime)` expose read-only
  dashboard routes for apps:
  - `GET /api/v1/dashboard/home`
  - `GET /api/v1/dashboard/state`
  - `GET /api/v1/dashboard/sdlc/receipts`
- `mount_operational_dashboard_router_from_env(app, env, runtime=...)` mounts
  those dashboard routes only when `MULLU_DASHBOARD_ENABLED=1`, uses
  `MULLU_DASHBOARD_PREFIX` when provided, and requires an explicit dashboard
  runtime so host apps do not construct dashboard state implicitly.
- The dashboard home payload includes plain UI fields: `status_label`,
  `count_summary`, `next_action`, `action_items`, `command_guidance`, and
  `start_here`, so apps can render user-facing status, command guidance, and a
  compact "what can I do now?" list without deriving it from workflow internals.

## Command Surface

```powershell
mcoi --help
mcoi-migrate-proofs --help
mcoi-swarm --audit-store .\swarm_audit.jsonl run-invoice .\invoice_request.json
mcoi-swarm --audit-store .\swarm_audit.jsonl get-run <run_id>
mcoi-swarm --audit-store .\swarm_audit.jsonl list-runs
mcoi-notes --note-store .\.mullusi\notes capture --kind WorkingNote --scope task --summary "bounded task note" --source-ref task:local --proof-state Unknown --trust-zone workspace --expires-at 2026-05-28T00:00:00+00:00
mcoi-notes --note-store .\.mullusi\notes retrieve "bounded task"
mcoi-notes --note-store .\.mullusi\notes record-rejected-delta --summary "Rejected unsafe note promotion" --source-ref task:local --evidence-ref proof:blocked
mcoi-notes --note-store .\.mullusi\notes queue-promotion <note_id>
mcoi-notes --note-store .\.mullusi\notes promote --note-id <note_id> --receipt .\promotion_receipt.json
mcoi-notes --note-store .\.mullusi\notes expire --now 2026-05-29T00:00:00+00:00
mcoi-notes --note-store .\.mullusi\notes rebuild-index
```

## Test Contract

Focused verification for this package surface:

```powershell
python -m pytest mcoi\tests\test_governance_sdk.py mcoi\tests\test_simple_platform.py mcoi\tests\test_simple_platform_fastapi_router.py mcoi\tests\test_swarm_package_metadata.py mcoi\tests\test_note_memory_projection_intelligence.py -q
```
