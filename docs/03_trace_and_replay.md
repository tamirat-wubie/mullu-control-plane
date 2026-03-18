# Trace and Replay

Trace is the causal record. Replay is a controlled reconstruction of that record.

## Trace rules

- Every planner decision, policy decision, execution attempt, and verification outcome MUST emit a trace entry.
- Trace entries MUST use stable field ordering and stable serialization.
- Trace entries MUST reference the state and registry snapshot used at the time of the event.
- Trace entries MUST preserve parent-child causality.

## Replay rules

- Replay MUST use a `ReplayRecord`.
- Replay MUST NOT re-run uncontrolled external effects.
- Replay MAY simulate, observe, or validate recorded effects only when the record explicitly permits it.
- Replay MUST prefer recorded actual effects over assumed effects.
- Replay MUST fail closed when trace data is missing, ambiguous, or out of order.

## Determinism rules

- Given the same trace snapshot and replay mode, replay output MUST be deterministic.
- Any nondeterministic source MUST be treated as an external effect and excluded from uncontrolled replay.
- Replay behavior that cannot be bounded MUST be documented as an accepted risk in the consuming implementation, not invented here.
