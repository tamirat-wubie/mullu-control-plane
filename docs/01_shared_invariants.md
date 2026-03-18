# Shared Invariants

Scope: MAF Core, MCOI Runtime, and Shared Contracts.

These invariants are mandatory and mechanically testable:

1. Same state + same registry + same goal = same plan.
2. No direct research-to-execution path is allowed.
3. Only admitted knowledge may enter planning.
4. Replay never re-runs uncontrolled external effects.
5. Actual effects override assumed effects.
6. Policy gate precedes execution.
7. No action is complete without verification closure.
8. Learning cannot mutate kernel invariants directly.

Rule interpretation:

- "Same state" means the same serialized state inputs used by the planner.
- "Same registry" means the same registry snapshot, including ordering.
- "Same goal" means the same goal identifier and goal payload.
- "Admitted knowledge" means knowledge accepted by the learning admission gate.
- "Verification closure" means a terminal verification result exists for the action.
- "Kernel invariants" are immutable within learning paths.

Any implementation that cannot test one of these rules at runtime or in integration tests is out of scope for compliance.
