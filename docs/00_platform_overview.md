# Platform Overview

> **In one box:** This is the map. It says which parts of the code count as the
> [control plane](GLOSSARY.md#control-plane) (the decide / check / record layer)
> and which names mean what (Mullu Govern vs Mullu vs Mullu Platform vs Mullu Control Plane).
> Read it when you're unsure *where a responsibility lives*. Brand new? Read the
> jargon-free [Plain-English Overview](explain/PLAIN_ENGLISH.md) first.
> *(Doc type: Reference.)*

Purpose: define the repository boundary for Mullu Govern and the Mullu Control Plane.
Governance scope: Milestone 0 shared foundation and Foundation Mode claim boundary.
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/PRODUCT_BOUNDARY.md`, `docs/01_shared_invariants.md`, `docs/02_shared_contracts.md`.
Invariants: shared meaning is defined once; Foundation Mode remains the current operating posture until promoted by witness; MAF Core and MCOI Runtime remain split; Mullu Govern remains the public product name; Mullu remains the suite/family name; Mullu Platform remains a developer and architecture term; Mullu Control Plane remains the admin/governance/deployment surface.

## Product Identity

Mullu Govern is the public governed-execution product by Mullusi. Mullu is the
suite/family name. Mullu Platform is reserved for developer, SDK, API,
deployment, and architecture contexts. This repository defines the Mullu Control
Plane surface for admin, governance, approval, trace, budget, lineage, and
deployment operation.

## Current Operating Posture

The current repository posture is [Foundation Mode](FOUNDATION_MODE.md):
private, local-first architecture hardening before deployment, customer access,
company formation, paid infrastructure, or patent filing. Platform capability
may be broad, but current proof work should remain narrow, local, reversible,
and receipt-backed until a later status witness promotes the project.

## Structure

- `Shared Contracts` define invariants, contract meaning, trace semantics, policy semantics, verification semantics, and learning admission semantics.
- `MAF Core` owns the general substrate, kernel-facing interfaces, and shared runtime primitives.
- `MCOI Runtime` owns computer-operation-specific observation and execution runtime surfaces.
- `Mullu Govern` remains product-facing and explains governed execution to users and buyers.
- `Mullu Control Plane` remains operator-facing and consumes traces, approvals, and status from the shared foundation.

The control-plane architecture treats every executable action as a governed
structure, not as a bare function call. The minimum action object is:

```text
Action := intent + actor + tenant + capability + policy + budget + time + evidence + receipt + closure
```

This makes Mullu Control Plane a higher-order structure over executable symbols:
features become capabilities, capabilities pass through policy and authority,
effects emit evidence and receipts, and closure produces the proof surface that
operators and downstream systems can inspect.

## Current repository boundary

- Shared definitions live in `docs/` and `schemas/`.
- Rust scaffold lives under `maf/rust/`.
- Python scaffold lives under `mcoi/`.
- Cross-runtime compatibility work lives under `integration/`.

## Repository Topology Decision

The current topology is one repository:

```text
repository: mullu-control-plane
product: Mullu Govern
company: Mullusi
```

This repository may contain governance engine, policy engine, witness engine,
receipt engine, deployment engine, agent runtime, skills, gateway, SDK, APIs,
documentation, tests, and operations while the project remains in Foundation
Mode. That is an intentional monorepo posture, not a final service boundary.

Do not split this repository while the active blocker is deployment evidence.
Repository splitting is deferred until public runtime evidence and usage create
real coordination pressure.

Split triggers:

1. Issue `#330` is closed by signed deployment witness evidence.
2. Deployment witness publication passes.
3. Public runtime health is verified by witness, conformance, proof, and audit
   endpoints.
4. First external users have arrived and the operator has evidence that repo
   size, review ownership, or deployable-service boundaries are causing real
   friction.
5. At least one scale trigger exists: 50+ active users, multiple teams, or
   multiple independently deployable services.

Possible future repositories, only after those triggers:

```text
mullu-govern-web
mullu-govern-api
mullu-control-plane-core
mullu-control-plane-sdk
mullusi-docs
```

Until then, Render or any other host may point at the current
`mullu-control-plane` runtime as the current platform runtime. That deployment
target does not by itself prove the final product architecture, public runtime
health, or repository-split readiness.

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
