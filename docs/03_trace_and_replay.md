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
- Replay harness reports MUST include per-frame expected hashes, actual hashes when computed, bounded reason codes, and a deterministic report hash.

## Determinism rules

- Given the same trace snapshot and replay mode, replay output MUST be deterministic.
- Any nondeterministic source MUST be treated as an external effect and excluded from uncontrolled replay.
- Replay behavior that cannot be bounded MUST be documented as an accepted risk in the consuming implementation, not invented here.
- Completed trace replay MUST verify frame sequence before invoking deterministic local handlers.

## Replay Harness Contract

| Field | Meaning |
|---|---|
| `replay_id` | Stable replay attempt identifier |
| `trace_id` | Source trace identifier |
| `trace_hash` | Recorded trace hash |
| `deterministic` | True only when every checked frame matches and no replay reason codes are present |
| `checked_frames` | Number of frames evaluated |
| `matched_frames` | Number of frames whose reconstructed hash matched the recorded hash |
| `mismatched_frames` | Number of frames with mismatch, unknown operation, sequence gap, or operation error |
| `reason_codes` | Bounded report-level causes |
| `frame_checks` | Per-frame operation, expected hash, actual hash, and reason code |
| `report_hash` | Deterministic hash over the report body |

STATUS:
  Completeness: 100%
  Invariants verified: trace causality, fail-closed replay, deterministic frame hashing, sequence verification, bounded reason codes, deterministic report hashing, operator replay report route
  Open issues: none
  Next action: persist replay reports for operator history queries
