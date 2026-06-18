# MafAbiCliContractWitness Contract

Purpose: define the Foundation Mode ABI/CLI witness required after
`MafReceiptParityWitness` and before any MAF Python-to-Rust runtime binding
claim can be reconsidered.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.

## Boundary

`MafAbiCliContractWitness` is a static contract witness. It records the MAF CLI
crate manifest, entry point, preceding parity witness, and open ABI gaps.

It does not execute the CLI, spawn a subprocess, import Rust into Python, call
external connectors, access secrets, write files, dispatch runtime work, or
claim ABI stability.

## Required Future Witnesses

1. `witness://maf/subprocess-effect-boundary`
2. `witness://maf/deterministic-fixture-parity`
3. `witness://maf/failure-receipt-path`

## Validator

Run:

```powershell
python scripts/validate_maf_abi_cli_contract_witness.py
```

The validator checks schema closure, source digests, open gap refs, authority
denials, receipt refs, summary counts, and secret-marker rejection.

## Status

Outcome: `AwaitingEvidence`.

No ABI stability, CLI execution, or runtime binding is claimed.
