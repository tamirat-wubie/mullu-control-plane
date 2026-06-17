# World Substrate Replay Witness Contract

Purpose: define a witness-only SWEWS-style world substrate replay boundary before any world snapshot, replay trace, sparse-cache truth, legal geometry, invariant registry, or planner/executor parity evidence can affect Mullu Control Plane governance claims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/82_cross_repo_opportunity_map.md`, `schemas/world_substrate_replay_witness.schema.json`, `schemas/world_state.schema.json`, `schemas/universal_action_orchestration.schema.json`, `schemas/life_meaning_judgment.schema.json`, `schemas/simulation_receipt.schema.json`, `schemas/effect_assurance.schema.json`, `schemas/sdlc_recovery_handoff_receipt.schema.json`.
Invariants: world substrate replay evidence stores no raw world snapshot or raw replay trace; it grants no live world service call, SQLite read, SQLite write, world mutation, replay execution, planner execution, executor execution, branch unquarantine, external endpoint call, secret access, filesystem write, terminal closure, or success authority.

## Boundary

`WorldSubstrateReplayWitness` is a witness record, not a world runtime adapter.

It may bind:

1. World snapshot digest refs.
2. Replay trace digest refs.
3. Sparse-cache truth refs.
4. Legal geometry refs.
5. Field derivation refs.
6. Invariant registry refs.
7. Planner/executor parity refs.
8. Branch quarantine refs.
9. UAO, LifeMeaningJudgment, SimulationReceipt, EffectAssurance, and SDLC recovery handoff refs.

It must not bind:

1. Raw world snapshots.
2. Raw replay traces.
3. Raw SQLite data.
4. Live world service calls.
5. SQLite reads or writes.
6. World mutation or replay execution.
7. Planner or executor execution.
8. External endpoint calls or secret access.
9. Branch unquarantine.
10. Publication, terminal closure, or success claims.

## Foundation Example

The Foundation Mode example is:

```text
examples/world_substrate_replay_witness.foundation.json
```

The validator is:

```powershell
python scripts\validate_world_substrate_replay_witness.py
```

Expected result:

```text
[PASS] world_substrate_replay_witness
```

## Authority Denials

The Foundation example requires these fields to remain `false`:

| Field | Denial |
| --- | --- |
| `live_world_service_call_performed` | no live world service call |
| `sqlite_read_performed` | no SQLite read |
| `sqlite_write_performed` | no SQLite write |
| `world_mutation_performed` | no world mutation |
| `replay_execution_performed` | no replay execution |
| `planner_execution_performed` | no planner execution |
| `executor_execution_performed` | no executor execution |
| `branch_unquarantined` | no branch unquarantine |
| `external_endpoint_called` | no external endpoint call |
| `secret_access_performed` | no secret access |
| `filesystem_write_performed` | no filesystem write authority |
| `raw_world_snapshot_stored` | no raw world snapshot retention |
| `raw_replay_trace_stored` | no raw replay trace retention |
| `terminal_closure_allowed` | no terminal closure |
| `success_claim_allowed` | no success claim |

## Safety Guards

The Foundation example requires:

| Field | Required value |
| --- | --- |
| `digest_refs_required` | `true` |
| `sparse_cache_truth_required` | `true` |
| `legal_geometry_required` | `true` |
| `invariant_registry_required` | `true` |
| `planner_executor_parity_required` | `true` |
| `branch_quarantine_required` | `true` |
| `raw_world_snapshot_retained` | `false` |
| `raw_replay_trace_retained` | `false` |
| `operator_review_required` | `true` |
| `incident_handoff_required_if_live` | `true` |

## Verification

Run:

```powershell
python scripts\validate_world_substrate_replay_witness.py
python -m pytest tests\test_validate_world_substrate_replay_witness.py -q
python scripts\validate_protocol_manifest.py
python scripts\proof_coverage_matrix.py --check
python scripts\validate_sdlc_artifact.py
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_world_substrate_replay_witness_20260617.json --strict
```

STATUS:
  Completeness: 100%
  Invariants verified: witness-only world replay evidence, digest-only world snapshot refs, digest-only replay trace refs, sparse-cache truth refs required, legal geometry refs required, invariant registry refs required, planner/executor parity required, branch quarantine required, no live world service call, no SQLite read or write, no world mutation, no replay execution, no raw world snapshot, no raw replay trace, no terminal closure
  Open issues: none
  Next action: use WorldSubstrateReplayWitness before any future world substrate replay proof admission gate
