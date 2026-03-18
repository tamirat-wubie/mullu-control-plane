# Mullu Platform

Mullu Platform is the umbrella repository for the shared substrate and the computer-operations vertical.

- **MAF Core** is the general agentic substrate.
- **MCOI Runtime** is the computer operating intelligence vertical.
- **Mullu Control Plane** is the operator-facing gateway, status, approvals, and trace surface.
- **Shared Contracts** are the canonical schemas and invariants used by both runtimes.

The repository keeps the substrate and the computer-operations vertical in a hard split. Shared meaning lives once in `docs/` and `schemas/`.

## Repository Tree

```text
mullu-platform/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── 00_platform_overview.md
│   ├── 01_shared_invariants.md
│   ├── 02_shared_contracts.md
│   ├── 03_trace_and_replay.md
│   ├── 04_policy_and_verification.md
│   ├── 05_learning_admission.md
│   ├── maf/
│   │   ├── 00_maf_overview.md
│   │   ├── 01_kernel_spec_v0.1.md
│   │   ├── 02_capability_model.md
│   │   └── 03_runtime_model.md
│   └── mcoi/
│       ├── 00_mcoi_overview.md
│       ├── 01_architecture.md
│       ├── 02_observer_model.md
│       ├── 03_execution_model.md
│       └── 04_operator_loop.md
├── schemas/
│   ├── README.md
│   ├── capability_descriptor.schema.json
│   ├── policy_decision.schema.json
│   ├── execution_result.schema.json
│   ├── trace_entry.schema.json
│   ├── replay_record.schema.json
│   ├── verification_result.schema.json
│   ├── learning_admission.schema.json
│   ├── environment_fingerprint.schema.json
│   ├── workflow.schema.json
│   └── plan.schema.json
├── maf/
│   └── rust/
│       ├── Cargo.toml
│       ├── crates/
│       │   ├── maf-kernel/
│       │   ├── maf-capability/
│       │   ├── maf-agent/
│       │   └── maf-cli/
│       └── tests/
├── mcoi/
│   ├── pyproject.toml
│   ├── mcoi_runtime/
│   │   ├── contracts/
│   │   ├── core/
│   │   ├── adapters/
│   │   ├── app/
│   │   └── persistence/
│   └── tests/
├── integration/
│   ├── contracts_compat/
│   └── cross_runtime_tests/
└── .github/
    └── workflows/
```

## Current Scope

- **Milestone 0 — Shared Foundation**: repository structure, top-level README, shared docs, shared schemas, empty package scaffolds, and CI placeholders.
- **Milestone 1 — MCOI Runtime v0.1**: typed Python contracts, invariant tests, evidence and state models, planning boundary scaffold, execution slice scaffold, observers, and operator loop skeleton.
