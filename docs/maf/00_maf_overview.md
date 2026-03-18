# MAF Overview

Purpose: state the role of MAF Core inside Mullu Platform.
Governance scope: Milestone 0 scaffold boundary.
Dependencies: shared docs in `docs/01_shared_invariants.md` through `docs/05_learning_admission.md`.
Invariants: MAF Core does not absorb MCOI-specific execution or observer responsibilities.

## Scope

MAF Core is the general substrate. It owns kernel-facing interfaces, capability handling, trace surfaces, replay surfaces, and policy-facing type boundaries that are not specific to computer operations.

## Out of scope

- Shell execution
- Filesystem and process observers
- Operator loop specifics
