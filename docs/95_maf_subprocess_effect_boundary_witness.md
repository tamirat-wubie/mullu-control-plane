# MafSubprocessEffectBoundaryWitness Contract

Purpose: define the Foundation Mode witness that closes the static subprocess
effect-boundary envelope for future MAF CLI binding without executing Rust,
subprocesses, shell commands, or command behavior.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.

## Boundary

`MafSubprocessEffectBoundaryWitness` follows `MafAbiCliContractWitness`.
It proves that a future Python-to-Rust CLI bridge has a denied-by-default
subprocess envelope before execution can be reconsidered.

The witness binds:

1. MAF ABI/CLI contract witness digests.
2. MAF Rust workspace and CLI scaffold digests.
3. Subprocess command-resolution, argv, cwd, environment, stdin, stdout,
   stderr, timeout, exit-code, filesystem, process/network, and failure
   receipt controls.
4. UAO and LifeMeaningJudgment refs.
5. Remaining future witness refs for deterministic fixture parity and failure
   receipt path.

## Denied Authority

The Foundation Mode example requires these to remain false:

1. CLI and subprocess execution authority.
2. Runtime binding and PyO3 authority.
3. Rust crate execution and Python-to-Rust import authority.
4. Shell invocation and child process spawn authority.
5. Connector, network, secret, stdin-secret, and environment-secret authority.
6. Raw stdout and stderr retention authority.
7. Filesystem write, runtime dispatch, and canonical state mutation authority.
8. Terminal closure and success claim authority.

## Validator

Run:

```powershell
python scripts/validate_maf_subprocess_effect_boundary_witness.py
```

The validator checks schema closure, exact refs, canonical source digests,
closed subprocess-boundary scope, denied effect controls, open fixture and
failure-path gaps, secret-marker rejection, summary counts, and
`AwaitingEvidence` status.

## Status

Outcome: `AwaitingEvidence`.

This closes only the subprocess effect-boundary witness prerequisite. Runtime
binding remains blocked until deterministic fixture parity and failure receipt
path witnesses exist.
