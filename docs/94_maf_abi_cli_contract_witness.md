# MafAbiCliContractWitness Contract

Purpose: define the Foundation Mode witness that records the MAF CLI/ABI
contract boundary without executing Rust, subprocesses, or command behavior.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.

## Boundary

`MafAbiCliContractWitness` is a static witness for the `maf-cli` boundary.
The current Rust CLI entry point is scaffold-only, so this contract records
intended command surfaces as `AwaitingEvidence`; it does not claim command
implementation or runtime binding.

The witness binds:

1. MAF Rust workspace manifest digest.
2. `maf-cli` crate manifest digest.
3. `maf-cli` entry-file digest.
4. MAF receipt parity witness refs.
5. Future command contracts with execution denied.

## Denied Authority

The Foundation Mode example requires these to remain false:

1. CLI execution authority.
2. Subprocess execution authority.
3. PyO3 binding authority.
4. Rust crate execution authority.
5. Python-to-Rust import authority.
6. Connector and network call authority.
7. Secret access and filesystem write authority.
8. Runtime dispatch and canonical state mutation authority.
9. Terminal closure and success claim authority.

## Validator

Run:

```powershell
python scripts/validate_maf_abi_cli_contract_witness.py
```

The validator checks schema closure, exact refs, canonical source digests,
scaffold-only scope, command execution denials, open gap refs, secret-marker
rejection, summary counts, and `AwaitingEvidence` status.

## Status

Outcome: `AwaitingEvidence`.

This closes only the static ABI/CLI contract witness prerequisite. Runtime
binding remains blocked until subprocess effect boundary, deterministic fixture
parity, and failure receipt path witnesses exist.
