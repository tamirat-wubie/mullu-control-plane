# MAF Deterministic Fixture Parity Witness

Purpose: record the Foundation Mode static fixture parity closure for the MAF CLI command descriptors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `MafSubprocessEffectBoundaryWitness`, MAF CLI scaffold refs, receipt schemas, deterministic descriptor digests, UAO, and LifeMeaningJudgment.
Invariants: fixture parity is static and digest-only; CLI execution, subprocess execution, runtime binding, raw fixture payload retention, filesystem writes, terminal closure, and success claims remain denied.

## Architecture

`MafDeterministicFixtureParityWitness` closes the deterministic fixture parity layer between the MAF CLI scaffold and the Python control-plane receipt contracts without executing Rust, spawning a subprocess, or retaining raw fixture payloads.

The witness binds three command descriptor fixtures:

| Command descriptor | Input contract | Expected output contract | Status |
| --- | --- | --- | --- |
| `verify-receipt-chain` | `schemas/worker_failure_receipt.schema.json` | `schemas/verification_result.schema.json` | `static_digest_parity` |
| `verify-kernel-proof` | `schemas/kernel_proof.schema.json` | `schemas/verification_result.schema.json` | `static_digest_parity` |
| `emit-transition-receipt` | `schemas/sdlc_transition_receipt.schema.json` | `schemas/worker_failure_receipt.schema.json` | `static_digest_parity` |

## Boundary

The witness is a read-only proof. It does not claim command behavior, subprocess behavior, Rust crate execution, PyO3 binding, Python imports of Rust, network calls, secret access, writes, runtime dispatch, canonical state mutation, terminal closure, or success authority.

The remaining future witness is:

| Future witness | Reason |
| --- | --- |
| `witness://maf/failure-receipt-path` | Runtime failure materialization still needs an independent receipt-path witness before executable MAF binding can be reconsidered. |

## Verification

Run:

```powershell
python scripts/validate_maf_deterministic_fixture_parity_witness.py
python -m pytest tests/test_validate_maf_deterministic_fixture_parity_witness.py -q
```

## Status

Solver outcome: `AwaitingEvidence`.

Closed layer: `witness://maf/deterministic-fixture-parity`.

Open layer: `witness://maf/failure-receipt-path`.
