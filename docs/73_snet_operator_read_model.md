# SNet Operator Read Model

> **In one box:** SNet is a local proof module for asking bounded questions
> about a symbol and seeing what evidence was created. This page shows an
> operator how to inspect SNet receipts without giving SNet any power to run
> tools, call connectors, change routes, write files, or claim final closure.
> *(Doc type: Reference.)*

Purpose: define the operator-facing SNet inspection boundary.
Governance scope: SNet recursive WH inquiry, read-only mesh projection, operator read-model validation, mesh receipt validation, SDLC integration gate, and no-authority runtime boundary.
Dependencies: `mcoi/mcoi_runtime/contracts/snet.py`, `mcoi/mcoi_runtime/snet/engine.py`, `mcoi/mcoi_runtime/snet/read_model.py`, `mcoi/mcoi_runtime/app/routers/snet.py`, `schemas/snet_operator_read_model.schema.json`, `examples/snet_operator_read_model.json`, `scripts/validate_snet_operator_read_model.py`, `schemas/snet_mesh_receipt.schema.json`, `scripts/validate_snet_mesh_receipt.py`, `examples/sdlc/requirement_snet_rsim_01_20260613.json`, and `examples/sdlc/design_snet_runtime_integration_gate_20260613.json`.
Invariants:
- SNet remains a local Foundation Mode proof module.
- SNet mesh receipts are non-terminal evidence.
- The operator read model exposes counts and receipt fields, not raw answers.
- SNet grants no execution, connector, route, filesystem, deployment, or external communication authority.
- SNet runtime routing is limited to `GET /api/v1/snet/operator/read-model`; no raw answer input, mutation method, connector handoff, filesystem write, or execution authority is admitted.

## Boundary

| Surface | Current state | Authority |
| --- | --- | --- |
| `SNetRecursiveMesh` | Local in-memory proof engine | No external effects |
| `build_snet_operator_read_model` | Bounded operator projection | Read-only |
| `SNetMeshReceipt` | Deterministic receipt over mesh counts and digest | Non-terminal evidence |
| `episode_replay` | Deterministic local replay descriptor for operator audit | Replay/audit only |
| `receipt_reconstruction` | Mesh-digest-to-receipt reconstruction summary | Read-only |
| `audit_explanation` | Bounded explanation of what SNet can and cannot prove | Read-only |
| `schemas/snet_operator_read_model.schema.json` | Operator projection schema | Validation only |
| `examples/snet_operator_read_model.json` | Saved bounded read-model example | Non-terminal evidence |
| `scripts/validate_snet_operator_read_model.py` | Schema, sample, and no-authority validator | Read-only |
| `schemas/snet_mesh_receipt.schema.json` | Receipt schema | Validation only |
| `scripts/validate_snet_mesh_receipt.py` | Schema and receipt validator | Read-only |
| `GET /api/v1/snet/operator/read-model` | Wired to deterministic seed-dependency operator projection | Read-only |
| Gateway routes | Not wired | Blocked |
| Connectors | Not wired | Blocked |
| Filesystem writes | Not granted by SNet | Blocked |
| Runtime dispatch | Not granted by SNet | Blocked |

## What Operators Can Inspect

| Field | Meaning |
| --- | --- |
| `surface` | Must be `read_only_snet_recursive_mesh`. |
| `mesh_digest` | Content-sensitive digest for the current mesh state. |
| `symbol_count` | Number of admitted local symbols in the mesh. |
| `question_count` | Number of generated WH questions. |
| `answer_count` | Number of stored candidate answers. |
| `metadata_count` | Number of extracted metadata records. |
| `relation_count` | Number of promoted symbol relations. |
| `unknown_count` | Number of first-class unknown records. |
| `contradiction_count` | Number of recorded contradiction records. |
| `settlement_counts` | Distribution across SNet settlement states. |
| `evidence_refs` | Receipt evidence references, including the mesh digest witness. |
| `episode_replay` | Replay mode, source refs, expected receipt, and denied live authorities. |
| `receipt_reconstruction` | Deterministic receipt reconstruction without raw answers or metadata. |
| `audit_explanation` | Operator-facing explanation of replay/audit scope and denied authorities. |
| `blocked_authorities` | Explicit list of SNet live execution, connector, filesystem, autonomous routing, and terminal closure authorities that remain blocked. |

The read model must not expose:

```text
raw answers
raw metadata values
execution authority
connector authority
route authority
filesystem authority
terminal closure authority
autonomous action routing authority
```

## Verification Commands

Run the operator read-model validator:

```powershell
python scripts/validate_snet_operator_read_model.py
```

Expected result:

```text
[PASS] snet_operator_read_model_schema
[PASS] snet_operator_read_model_sample
[PASS] snet_operator_read_model_no_authority_boundary
STATUS: passed
```

Run the receipt validator:

```powershell
python scripts/validate_snet_mesh_receipt.py
```

Expected result:

```text
[PASS] snet_mesh_receipt_schema
[PASS] snet_mesh_receipt_sample
[PASS] snet_mesh_receipt_no_authority_boundary
STATUS: passed
```

Run the focused runtime and receipt tests:

```powershell
python -m pytest mcoi/tests/test_snet_recursive_mesh.py mcoi/tests/test_snet_router.py tests/test_validate_snet_mesh_receipt.py tests/test_validate_snet_operator_read_model.py -q
```

Run the SDLC artifact gate for the SNet requirement and design decision:

```powershell
python scripts/validate_sdlc_artifact.py
```

## Promotion Gate

SNet may be considered for a runtime route only after all of these are true:

| Required evidence | Current state |
| --- | --- |
| Design decision for bounded read-only runtime wiring | Satisfied by `examples/sdlc/design_snet_runtime_integration_gate_20260613.json` |
| Security review for route exposure | Satisfied by no-authority route tests and SDLC security validation |
| Rollback and recovery plan | Satisfied by route removal and focused SNet validator rerun path |
| Live evidence receipt proving no authority expansion | Satisfied by `mcoi/tests/test_snet_router.py` and workspace governance preflight receipt |
| Workspace governance preflight receipt | Required before closure claim |

Until a separate future witness exists, SNet stays read-only and cannot accept raw answers, connector requests, filesystem writes, gateway exposure, autonomous dispatch, or terminal-closure claims.

## Failure Handling

| Failure | Required response |
| --- | --- |
| Receipt schema validation fails | Treat the mesh receipt as inadmissible. |
| `raw_answers_exposed=true` | Block the receipt. |
| Any authority field is `true` | Block the receipt. |
| `mesh_digest` missing or malformed | Block the receipt. |
| Settlement totals do not match symbol count | Block the receipt. |
| Additional runtime route is proposed without a new promotion gate | Classify as `GovernanceBlocked`. |

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the SNet requirement | [SNet SDLC requirement](../examples/sdlc/requirement_snet_rsim_01_20260613.json) |
| See the SNet runtime integration gate | [SNet runtime integration gate](../examples/sdlc/design_snet_runtime_integration_gate_20260613.json) |
| Inspect a saved operator read-model example | [SNet operator read-model example](../examples/snet_operator_read_model.json) |
| Validate the operator read-model contract | [SNet operator read-model validator](../scripts/validate_snet_operator_read_model.py) |
| Validate the SNet receipt contract | [SNet receipt validator](../scripts/validate_snet_mesh_receipt.py) |
| Understand the broader substrate plan | [Operating Substrate Integration Plan](72_operating_substrate_integration_plan.md) |
| See the whole documentation map | [Start Here](START_HERE.md) |

Back to [Start Here](START_HERE.md)

STATUS:
  Completeness: 100%
  Invariants verified: read-only SNet route boundary, bounded operator projection, non-terminal receipt, no raw-answer exposure, no authority grant, connector/filesystem/execution surfaces remain blocked
  Open issues: gateway, connector, filesystem, execution, and terminal-closure integration remain AwaitingEvidence
  Next action: use the validator commands above before any SNet closure claim
