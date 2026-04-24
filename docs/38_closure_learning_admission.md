# Closure Learning Admission

Closure learning admission is the bridge from terminal closure memory to reusable
knowledge.

It does not write semantic or procedural memory directly. It issues a
`LearningAdmissionDecision` that downstream memory stores must check before
using a closure-derived knowledge item in planning.

## Purpose

The layer prevents effect-bearing command history from becoming reusable
knowledge just because it was recorded.

The required chain is:

```text
TerminalClosureCertificate
  -> Episodic MemoryEntry
  -> ClosureLearningAdmissionGate
  -> LearningAdmissionDecision
  -> semantic/procedural candidate use
```

## Contracts

| Contract | Role |
| --- | --- |
| `TerminalClosureCertificate` | Names final command disposition and evidence |
| `MemoryEntry` | Holds append-only episodic closure memory |
| `LearningAdmissionDecision` | Decides whether derived knowledge may enter planning |

## Admission Rules

| Terminal disposition | Required memory | Decision |
| --- | --- | --- |
| `committed` | `execution_success` with `trust_class=trusted` | `admit` |
| `compensated` | `compensation_success` with `trust_class=trusted_compensation` | `admit` |
| `accepted_risk` | accepted-risk episodic record | `defer` |
| `requires_review` | review or failure record | `reject` |

## Mandatory Invariants

- No closure-derived knowledge may enter planning without a
  `LearningAdmissionDecision`.
- A terminal certificate must reference the same episodic `memory_entry_id`
  being evaluated.
- Accepted-risk closure is not reusable knowledge; it is deferred until the
  risk is resolved.
- Review-required closure is rejected from learning admission.
- Compensation learning requires a successful compensation memory source.

## Non-Goals

- This layer does not generalize semantic rules.
- This layer does not create runbooks.
- This layer does not mutate kernel invariants.
- This layer does not treat accepted risk as successful operation.

## Runtime Entry Point

`ClosureLearningAdmissionGate.decide(...)` takes:

- a terminal closure certificate,
- the referenced episodic memory entry,
- the target learning scope,
- and the proposed downstream use.

It returns and stores a `LearningAdmissionDecision`.

Only `LearningAdmissionStatus.ADMIT` may be consumed by semantic or procedural
memory writers.
