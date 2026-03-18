# Capability Model

Purpose: state how MAF Core treats shared capability descriptors.
Governance scope: shared contract adoption.
Dependencies: `docs/02_shared_contracts.md`, `schemas/capability_descriptor.schema.json`.
Invariants: MAF Core uses the canonical `CapabilityDescriptor` without reinterpretation.

## Rules

- Capability meaning is defined by the shared contract.
- MAF Core may index capabilities, but it must not redefine shared fields.
- MCOI-specific capability semantics remain outside this document.
