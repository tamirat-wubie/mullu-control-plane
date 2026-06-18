# MafReceiptParityWitness Contract

Purpose: define the Foundation Mode witness that records MAF Python schema to
Rust crate receipt-surface parity by digest only.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.

## Boundary

`MafReceiptParityWitness` is a static evidence contract. It does not execute
Rust, import Rust into Python, call a CLI, spawn a subprocess, call a connector,
or mutate runtime state.

The witness maps:

1. Python schema surfaces in `schemas/*.schema.json`.
2. Rust MAF crate manifests and entry files under `maf/rust/crates/*`.
3. Explicit parity mappings with open gap refs.
4. Authority-denial flags that keep runtime binding claims blocked.

## Required Future Witnesses

Runtime binding remains `AwaitingEvidence` until all of these have independent
evidence:

1. `witness://maf/abi-cli-contract`
2. `witness://maf/subprocess-effect-boundary`
3. `witness://maf/deterministic-fixture-parity`
4. `witness://maf/failure-receipt-path`

## Denied Authority

The Foundation Mode example requires these to remain false:

1. PyO3 binding authority.
2. Subprocess execution authority.
3. CLI execution authority.
4. Rust crate execution authority.
5. Python-to-Rust import authority.
6. External connector and network call authority.
7. Secret access and filesystem write authority.
8. Runtime dispatch and canonical mutation authority.
9. Terminal closure and success claim authority.

## Validator

Run:

```powershell
python scripts/validate_maf_receipt_parity_witness.py
```

The validator checks schema closure, exact refs, canonical source digests,
open parity gaps, authority denials, secret-marker rejection, summary counts,
and `AwaitingEvidence` status.

## Status

Outcome: `AwaitingEvidence`.

No runtime binding is claimed. The contract closes the static witness gap only.
