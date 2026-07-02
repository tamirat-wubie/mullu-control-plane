# Causal Repair Service

Purpose: define the reusable proof-only causal repair service for governed
workflow failures.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `mcoi/causal_repair/service.py`,
`mcoi/mcoi_runtime/core/causal_repair.py`, and
`schemas/causal_repair_service_receipt.schema.json`.
Invariants: classification does not execute rollback, compensation, connector
effects, file writes, branch pushes, pull request creation, merge, deployment,
or external writes.

## Architecture

The service sits above the existing low-level causal repair engine. It does not
replace action admission, durable episode tracking, or rollback execution.
Instead, it converts common workflow failures into a stable repair proposal
receipt:

1. Detect a known failure class.
2. Classify cause, effect, reversibility, and repair strategy.
3. Declare required rollback or compensation proof.
4. Generate the next repair proof action.
5. Stop before live repair execution.

## Failure Coverage

| Failure | Cause class | Repair strategy | Outcome |
| --- | --- | --- | --- |
| `failed_patch_plan` | `planning_contract_failure` | `exact_rollback` | `AwaitingEvidence` |
| `failed_test` | `verification_failure` | `exact_rollback` | `AwaitingEvidence` |
| `stale_evidence` | `evidence_freshness_failure` | `none_required` | `AwaitingEvidence` |
| `missing_approval` | `approval_gap` | `escalate` | `AwaitingEvidence` |
| `rollback_impossible` | `repair_authority_gap` | `forbid` | `GovernanceBlocked` |
| `ci_failure` | `ci_verification_failure` | `version_restore` | `AwaitingEvidence` |
| `unsafe_browser_evidence` | `unsafe_evidence_origin` | `none_required` | `AwaitingEvidence` |

## Commands

```powershell
python scripts/run_causal_repair_service.py --json
python scripts/validate_causal_repair_service_receipt.py --json
python -m pytest tests/test_causal_repair_service.py -q
```

## Receipt

Default output:

```text
.change_assurance/causal_repair_service_receipt.json
```

The receipt is schema-backed by:

```text
urn:mullusi:schema:causal-repair-service-receipt:1
```

## Boundaries

Constructive deltas:

1. Adds reusable failure classification.
2. Adds explicit repair proof obligations.
3. Reuses existing repair engine vocabulary.
4. Blocks execution overclaims.

Fracture deltas:

1. No repair action execution.
2. No file write beyond the requested receipt artifact.
3. No branch push, pull request creation, merge, deployment, connector call, or external write.
