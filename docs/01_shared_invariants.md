# Shared Invariants

> **In one box:** The promises the system can *never* break, written as plain
> testable rules (e.g. "the same situation always produces the same plan",
> "nothing researched can run without passing the gate"). These are the safety
> guarantees in their rawest form — see them explained with an analogy in the
> [Plain-English Overview](explain/PLAIN_ENGLISH.md). Unknown word? →
> [Glossary](GLOSSARY.md). *(Doc type: Reference.)*

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
9. Executable actions are incomplete unless their governing structure is present
   or the non-closure is explicitly recorded.

Rule interpretation:

- "Same state" means the same serialized state inputs used by the planner.
- "Same registry" means the same registry snapshot, including ordering.
- "Same goal" means the same goal identifier and goal payload.
- "Admitted knowledge" means knowledge accepted by the learning admission gate.
- "Verification closure" means a terminal verification result exists for the action.
- "Kernel invariants" are immutable within learning paths.
- "Governing structure" means the action is bound to intent, actor, tenant,
  capability, policy, budget or resource limits, time, evidence, receipt, and
  closure state.

Any implementation that cannot test one of these rules at runtime or in integration tests is out of scope for compliance.
