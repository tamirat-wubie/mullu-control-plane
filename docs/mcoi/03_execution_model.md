# Execution Model

Purpose: reserve the execution boundary for MCOI Runtime.
Governance scope: Milestone 0 structure only.
Dependencies: shared policy, execution, and verification semantics.
Invariants: execution follows policy; adapters do not mutate committed state directly.

## Reserved execution surfaces

- Template validation
- Dispatcher
- Controlled executor adapters
- Execution result capture
