# Learning Admission

Learning admission controls what knowledge may enter planning.

## Admission rules

- Learning MUST produce a `LearningAdmissionDecision` before new knowledge is used in planning.
- Only `admit` status MAY promote knowledge into planning inputs.
- `reject` and `defer` statuses MUST block planning use.
- Admission decisions MUST be explicit, traceable, and stable in serialization.

## Boundary rules

- Learning MUST NOT mutate kernel invariants directly.
- Learning MUST NOT bypass policy gates or verification closure.
- Learning MUST NOT create hidden planning inputs.
- Learning outputs MUST identify the knowledge item they govern.

## Testability rules

- An implementation MUST be able to prove whether a knowledge item was admitted.
- An implementation MUST be able to prove whether planning consumed admitted knowledge only.
- An implementation that cannot distinguish admitted from non-admitted knowledge is non-compliant.
