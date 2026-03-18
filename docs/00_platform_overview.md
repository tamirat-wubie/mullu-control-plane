# Platform Overview

Purpose: define the repository boundary for Mullu Platform.
Governance scope: Milestone 0 shared foundation.
Dependencies: `docs/01_shared_invariants.md`, `docs/02_shared_contracts.md`.
Invariants: shared meaning is defined once; MAF Core and MCOI Runtime remain split.

## Structure

- `Shared Contracts` define invariants, contract meaning, trace semantics, policy semantics, verification semantics, and learning admission semantics.
- `MAF Core` owns the general substrate, kernel-facing interfaces, and shared runtime primitives.
- `MCOI Runtime` owns computer-operation-specific observation and execution runtime surfaces.
- `Mullu Control Plane` remains operator-facing and consumes traces, approvals, and status from the shared foundation.

## Current repository boundary

- Shared definitions live in `docs/` and `schemas/`.
- Rust scaffold lives under `maf/rust/`.
- Python scaffold lives under `mcoi/`.
- Cross-runtime compatibility work lives under `integration/`.

## Deferred work

- No runtime behavior is implemented in Milestone 0.
- No planner, policy engine, executor, or observer logic is implemented in Milestone 0.
