# Governed Operations Kernel v1

Purpose: define the non-invasive governed-operations read model for Mullu Control Plane.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `gateway/governed_operations.py`, `schemas/governed_operations_snapshot.schema.json`, runtime conformance, deployment witness, audit anchors, authority obligation witness, and existing receipt projections.
Invariants: missing evidence is a gap, closure requires evidence, drift compares declared state to observed state, and v1 exposes no mutation endpoint.

## Architecture

The kernel is a read-model layer over existing subsystems:

| Component | Responsibility | Mutation authority |
| --- | --- | --- |
| `LoopRegistry` | Declares governed operational loops and their target states. | none |
| `ReceiptRecord` | Projects existing subsystem evidence into one receipt shape. | none |
| `ClosureContract` | Defines completion conditions, required evidence, rollback path, and approval boundary. | none |
| `DriftCheck` | Compares declared state to observed state. | none |
| `GapRecord` | Turns missing evidence, drift, or unresolved authority into first-class blockers. | none |
| `ReadinessSnapshot` | Emits a schema-backed platform readiness view. | none |

## Registered Loops

| Loop | Declared state | Required evidence |
| --- | --- | --- |
| `deployment_witness` | `witnessed` | deployment witness, runtime health, proof verification, domain declaration |
| `runtime_conformance` | `conformant` | runtime conformance certificate |
| `audit_proof_verification` | `verified` | audit anchor and proof verification |
| `authority_obligations` | `clear` | authority responsibility witness |
| `cognitive_outcome_loop` | `closed` | outcome receipt and verification |
| `governed_code_change_loop` | `closed` | tests, validators, rollback evidence |
| `adapter_promotion_loop` | `certified` | adapter certification, receipt contract, rollback evidence |

## Algorithm

1. Load the loop registry.
2. Collect existing evidence refs from receipts and loop-local read models.
3. Compare declared and observed state for each loop.
4. Evaluate closure contracts.
5. Emit blocking gaps for missing required evidence or drift.
6. Derive readiness class:

| Class | Meaning |
| --- | --- |
| `class_a` | all loops closed, no gaps |
| `class_b` | verified with non-blocking gaps |
| `class_c` | degraded without blocking evidence |
| `class_d` | blocked by missing evidence, drift, or authority debt |

## Read-Only API

`GET /governed-operations/read-model`

This endpoint reads existing gateway evidence and returns a `ReadinessSnapshot`. It does not publish, deploy, dispatch, approve, certify, or close anything.

## Verification

Focused contract tests:

```powershell
python -m pytest tests/test_gateway/test_governed_operations.py
```

Schema contract:

```powershell
schemas/governed_operations_snapshot.schema.json
```

## Status

Outcome: `SolvedVerified` when focused tests, schema validation, and workspace governance preflight pass.
