# Architecture

Purpose: define the Milestone 0 architectural split for MCOI Runtime.
Governance scope: package boundary only.
Dependencies: shared contracts and shared invariants.
Invariants: planner or policy logic does not live in adapters.

## Module split

- `contracts/` holds typed runtime surfaces built from shared contracts.
- `core/` holds deterministic runtime orchestration boundaries.
- `adapters/` holds environment-specific execution and observation adapters.
- `app/` holds the operator-facing runtime entry surface.
- `persistence/` holds local state, trace, and replay persistence boundaries.
