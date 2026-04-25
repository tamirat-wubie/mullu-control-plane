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

## Planning consumption proof

Planning may use the ordinary lifecycle/class boundary for local runtime checks,
but any path that claims learning-governed knowledge must use an explicit
`LearningAdmissionDecision`.

The proof boundary is:

```text
PlanningKnowledge
  -> lifecycle/class check
  -> LearningAdmissionDecision lookup
  -> status == admit
  -> planning input admitted
```

`defer`, `reject`, missing, duplicate, or mismatched admission decisions MUST
block planning use with an explicit rejection reason.

Semantic memory entries projected into planning MUST carry the same
`admission_id` that admitted the semantic version. This keeps the write-time
learning gate and the planning-time proof gate on the same causal chain.
