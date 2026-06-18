# MAF Failure Receipt Path Witness

Purpose: record the Foundation Mode static failure receipt path closure for the MAF CLI command descriptors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `MafDeterministicFixtureParityWitness`, MAF CLI scaffold refs, receipt schemas, deterministic path descriptors, UAO, and LifeMeaningJudgment.
Invariants: failure receipt path closure is static and digest-only; runtime binding, CLI execution, subprocess execution, command behavior, raw failure payload retention, filesystem writes, terminal closure, and success claims remain denied.

## Architecture

`MafFailureReceiptPathWitness` closes the last static MAF runtime-binding prerequisite by binding failure materialization paths for the three static command descriptors already admitted by `MafDeterministicFixtureParityWitness`.

The witness binds three failure path descriptors:

| Command descriptor | Failure source | Failure receipt path | Status |
| --- | --- | --- | --- |
| `verify-receipt-chain` | `fixture://maf/verify-receipt-chain/static-digest-v1` | `schemas/worker_failure_receipt.schema.json` via `schemas/verification_result.schema.json` | `static_failure_receipt_path` |
| `verify-kernel-proof` | `fixture://maf/verify-kernel-proof/static-digest-v1` | `schemas/kernel_proof.schema.json` via `schemas/verification_result.schema.json` | `static_failure_receipt_path` |
| `emit-transition-receipt` | `fixture://maf/emit-transition-receipt/static-digest-v1` | `schemas/sdlc_transition_receipt.schema.json` via `schemas/worker_failure_receipt.schema.json` | `static_failure_receipt_path` |

## Boundary

The witness closes `witness://maf/failure-receipt-path` but does not claim runtime binding, command behavior, subprocess behavior, Rust crate execution, PyO3 binding, Python imports of Rust, network calls, secret access, writes, runtime dispatch, canonical state mutation, terminal closure, or success authority.

Runtime binding becomes reconsiderable only through a later implementation thread with its own UAO, LifeMeaningJudgment, execution evidence, rollback evidence, and receipt chain. This witness is not that implementation.

## Verification

Run:

```powershell
python scripts/validate_maf_failure_receipt_path_witness.py
python -m pytest tests/test_validate_maf_failure_receipt_path_witness.py -q
```

## Status

Solver outcome: `AwaitingEvidence`.

Closed layer: `witness://maf/failure-receipt-path`.

Runtime binding claim: denied.
