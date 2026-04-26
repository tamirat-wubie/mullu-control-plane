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

## Status (2026-04-26)

Milestone 0 is complete. The platform now implements the governed
runtime end-to-end. See `docs/CORE_STRUCTURE.md` for the verified
state of the foundational layer (MAF/MCOI split, contracts, schemas,
layering) and the load-bearing-claims spec set:

- `docs/CORE_STRUCTURE.md` — Foundation (this layer)
- `docs/LEDGER_SPEC.md` — Hash-chain audit trail + external verifier
- `docs/MAF_RECEIPT_COVERAGE.md` — Transition-receipt coverage
- `docs/GOVERNANCE_GUARD_CHAIN.md` — Eight-guard chain semantics

Each spec includes a compliance posture table that distinguishes
verified from aspirational. The platform's architectural claims are
load-bearing top-to-bottom.
