# Platform Overview

Purpose: define the repository and product boundary for Mullu.
Governance scope: Milestone 0 shared foundation.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/01_shared_invariants.md`, `docs/02_shared_contracts.md`.
Invariants: shared meaning is defined once; MAF Core and MCOI Runtime remain split; Mullu remains the flagship product name; Mullu Platform remains a developer and architecture term; Mullusi remains the company and ecosystem brand.

## Product Identity

Mullu is the flagship product under Mullusi. It is the public product name for
personal work handling, enterprise operation, capability deployment, connector
execution, audit receipts, and governed runtime promotion.

Mullu Platform is reserved for developer, SDK, API, deployment, and architecture
contexts. Customer-facing surfaces should follow the `Mullu [Surface]` pattern:
`Mullu Inspect`, `Mullu CLI`, `Mullu Code`, and future product surfaces.

## Structure

- `Shared Contracts` define invariants, contract meaning, trace semantics, policy semantics, verification semantics, and learning admission semantics.
- `MAF Core` owns the general substrate, kernel-facing interfaces, and shared runtime primitives.
- `MCOI Runtime` owns computer-operation-specific observation and execution runtime surfaces.
- `Mullu Control Plane` remains operator-facing and consumes traces, approvals, and status from the shared foundation.
- `Mullu` remains the public product; `Mullu Platform` remains the developer and architecture term.

## Current repository boundary

- Shared definitions live in `docs/` and `schemas/`.
- Rust scaffold lives under `maf/rust/`.
- Python scaffold lives under `mcoi/`.
- Cross-runtime compatibility work lives under `integration/`.

## Deferred work

- No runtime behavior is implemented in Milestone 0.
- No planner, policy engine, executor, or observer logic is implemented in Milestone 0.
