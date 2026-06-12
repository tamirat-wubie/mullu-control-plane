# Nested Mind Activation Boundary - 2026-06-12

Purpose: define what the merged `external/nested-mind-platform` import changes now, what remains inactive, and which activation lane is allowed next.
Governance scope: Nested Mind import boundary, Mullu runtime authority, SDLC requirement evidence, read-only projection bridge, governed `record_observation` staging, and future memory topology activation.
Dependencies: `docs/design/nested-mind-integration-seam.md`, `docs/runbooks/nested-mind-record-observation-staging.md`, `external/nested-mind-platform`, `mcoi/mcoi_runtime/contracts/nested_mind.py`, `mcoi/mcoi_runtime/adapters/nested_mind.py`, `scripts/validate_nested_mind_p3_readiness.py`.
Invariants: imported code does not become active runtime authority by presence alone; mutation remains default-off; no public protocol claim is made without schema and manifest evidence; no system-of-record switch occurs without a governed decision.

## Decision

The merge improves the platform, but the immediate value is source ownership and evidence availability, not automatic runtime activation.

`external/nested-mind-platform` is now the owned Nested Mind service boundary. Mullu remains the outer governance and orchestration layer. Nested Mind may become the governed memory substrate only through staged evidence:

```text
source imported
-> local build/test witness
-> read-only projection witness
-> governed record_observation staging witness
-> P3 readiness evidence
-> memory topology activation decision
```

The next active lane is the existing Mullu-side Nested Mind bridge, not direct crate transplantation into the Mullu runtime.

## Crate Activation Map

| Surface | Present after merge | Activation decision | Reason |
| --- | --- | --- | --- |
| `mind-core` | yes | Reference and service-owned kernel first | It owns Nested Mind invariants, commits, lawbook validation, and projection construction. It should not replace Mullu contracts until type vocabulary is reconciled. |
| `mind-store-sqlite` | yes | Staging/local persistence candidate | It can back service evidence during staging. It is not yet the Mullu system of record. |
| `mind-api` | yes | Staging endpoint only after local service witness | It exposes projection and proposal routes, so it crosses external effect and authorization boundaries. |
| `mind-worker` | yes | Keep inactive | Always-on workers require lease, idempotency, secret, and rollback evidence before activation. |
| `mind-connectors` | yes | Keep internal to Nested Mind until mapped | Connector authority must be mapped to Mullu UAO receipts before live use. |
| `mind-cli` | yes | Safe for local evidence and operator rehearsal | CLI runs are bounded, inspectable, and useful for build/test/readiness evidence. |

## Allowed Next Activation

The next permitted step is a staging-only `record_observation` evidence run through the existing bridge:

```text
Mullu receipt / authority receipt
-> NestedMindProposalEvidence
-> NestedMindObservationProposalPlan
-> dry-run submit
-> optional staging submit
-> read-only reconcile
-> append-only local evidence store
-> P3 readiness validator
```

Allowed commands are documented in `docs/runbooks/nested-mind-record-observation-staging.md`.

## Blocked Until Evidence Exists

These actions remain blocked:

1. Running `mind-worker` as a standing service.
2. Treating Nested Mind as the Mullu system of record.
3. Mapping tenants, projects, or tasks to child minds.
4. Allowing lawbook migration or child-mind creation from Mullu.
5. Adding public `schemas/nested_mind_*.schema.json` protocol files.
6. Persisting raw Nested Mind response bodies, bearer tokens, or secret values.
7. Claiming production readiness for the Nested Mind service.

## Requirement Packet

`examples/sdlc/requirement_nested_mind_activation_boundary_20260612.json` records the governed requirement for this boundary.

The requirement classifies activation as high risk because future steps can change memory authority, external service behavior, credentials, and long-running workers. This document itself is a documentation and governance artifact; it does not activate runtime behavior.

## Evidence Required Before P3

1. Local Rust workspace build/test witness for `external/nested-mind-platform`.
2. Mullu-side nested-mind bridge tests passing.
3. Dry-run observation plan output with no network write.
4. Optional staging submit evidence with `MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=true` only during the submit window.
5. Read-after-write reconciliation evidence.
6. `scripts/validate_nested_mind_p3_readiness.py` passing against the append-only evidence store.
7. Workspace governance preflight receipt.

## Settlement Witness - 2026-06-12

Repository settlement is verified at Git commit `73606cf30`, the merge commit
for the Nested Mind activation boundary.

Verified local state:

1. `main` is aligned with `origin/main`.
2. Focused Nested Mind tests passed:

   ```powershell
   python -m pytest tests/test_nested_mind_integration.py tests/test_nested_mind_observation_submitter_env.py tests/test_nested_mind_observation_submitter.py tests/test_nested_mind_staging_harness.py -q
   ```

   Result: `43 passed`.

3. Imported Nested Mind Rust workspace tests passed:

   ```powershell
   cd external/nested-mind-platform
   cargo test --workspace
   cargo test --workspace -- --list
   ```

   Result: `cargo test --workspace` passed, and the workspace test inventory
   reported `122` tests across `mind-core`, `mind-connectors`,
   `mind-store-sqlite`, `mind-api`, `mind-cli`, and `mind-worker`.

4. Workspace governance preflight passed:

   ```powershell
   python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt-nested-mind-settlement-20260612.json
   ```

   Result: `144` checks passed, and the saved receipt validated with
   `scripts/validate_workspace_governance_preflight_receipt.py`.

5. Live activation gates were absent in the local shell:

   ```text
   MULLU_NESTED_MIND_ENABLED=absent
   MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED=absent
   MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=absent
   MULLU_NESTED_MIND_BASE_URL=absent
   MULLU_NESTED_MIND_BEARER_TOKEN=absent
   ```

6. Local `mind-api` does not satisfy live staging evidence by itself. The
   Mullu bridge requires HTTPS and the governed HTTP connector blocks loopback,
   private, and metadata-network targets. A valid live witness therefore needs
   a real HTTPS staging endpoint and bounded token, not localhost or a private
   workstation URL.

Settlement result: `SolvedVerified`.

Live activation result: `AwaitingEvidence`.

## Outcome

Current import state: `SolvedVerified`.

Runtime activation state: `AwaitingEvidence`.

The merge makes the platform better because it gives Mullu an owned, testable Nested Mind substrate. It does not make the platform fully integrated yet. The correct next process is to produce one staging evidence chain, then decide whether P3 memory topology should attach to Nested Mind.
