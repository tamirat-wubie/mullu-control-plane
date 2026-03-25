# Mullu Platform

Mullu Platform is the umbrella repository for the shared substrate and the
computer-operations vertical.

- **MAF Core** is the general agentic substrate.
- **MCOI Runtime** is the computer operating intelligence vertical.
- **Mullu Control Plane** is the operator-facing gateway, status, approvals, and
  trace surface.
- **Shared Contracts** are the canonical schemas and invariants used by both
  runtimes.

The repository keeps the substrate and the computer-operations vertical in a hard
split. Shared meaning lives once in `docs/` and `schemas/`.

## Repository Tree

```text
mullu-platform/
|- README.md
|- LICENSE
|- .gitignore
|- docs/
|- schemas/
|- maf/
|  \- rust/
|- mcoi/
|  |- pyproject.toml
|  |- examples/
|  |- mcoi_runtime/
|  |  |- contracts/
|  |  |- core/
|  |  |- adapters/
|  |  |- app/
|  |  |- persistence/
|  |  \- pilot/
|  \- tests/
|- integration/
|- scripts/
|- tests/
\- .github/
```

## Current State

- **Shared foundation** is implemented: canonical docs and schemas define
  cross-runtime meaning.
- **MCOI Runtime** is an internal-alpha governed runtime with contracts,
  execution adapters, operator loop orchestration, explicit verification closure,
  persistence, replay validation, runbooks, provider registry, workflows,
  memory tiers, skills, and pilot/domain packs.
- **MAF Core** is compileable and test-backed on the Rust side, with shared
  kernel types, lifecycle/state-machine contracts, supervision surfaces, and
  learning/governance type layers.

## Practical Notes

- The CLI entrypoint is `mcoi`.
- Portable example requests live under `mcoi/examples/`.
- Runtime limitations and intentional gaps are tracked in
  `KNOWN_LIMITATIONS_v0.1.md`.
