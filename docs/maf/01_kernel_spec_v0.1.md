# Kernel Spec v0.1

Purpose: define the Milestone 0 kernel scaffold boundary for MAF Core.
Governance scope: interface surface only.
Dependencies: shared contracts and shared invariants.
Invariants: kernel responsibilities remain explicit and deterministic.

## Kernel boundary

- Accept canonical shared contracts without redefining them.
- Expose deterministic interfaces for capability lookup, trace emission, replay admission, and policy decision consumption.
- Defer implementation behavior to Milestone 2.
