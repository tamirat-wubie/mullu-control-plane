# Shared Contracts

These are the canonical cross-cutting contracts. MAF Core and MCOI Runtime must not redefine them.

## CapabilityDescriptor

Purpose: declare what a subject can do.

Required fields, in order:
`capability_id`, `subject_id`, `name`, `version`, `scope`, `constraints`

Rules:

- `capability_id` and `subject_id` MUST be stable identifiers.
- `constraints` MUST be explicit and bounded.
- Contract consumers MUST treat missing required fields as invalid.

## PolicyDecision

Purpose: record the policy gate outcome before execution.

Required fields, in order:
`decision_id`, `subject_id`, `goal_id`, `status`, `reasons`, `issued_at`

Rules:

- `status` MUST be one of `allow`, `deny`, or `escalate`.
- `reasons` MUST be explicit and machine readable.
- A denied or escalated decision MUST block execution.

## ExecutionResult

Purpose: record the observed outcome of an attempted action.

Required fields, in order:
`execution_id`, `goal_id`, `status`, `actual_effects`, `assumed_effects`, `started_at`, `finished_at`

Rules:

- `status` MUST be one of `succeeded`, `failed`, or `cancelled`.
- `actual_effects` MUST override conflicting `assumed_effects`.
- If no actual effect occurred, the result MUST say so explicitly.

## TraceEntry

Purpose: provide an ordered audit record for one causal step.

Required fields, in order:
`trace_id`, `parent_trace_id`, `event_type`, `subject_id`, `goal_id`, `state_hash`, `registry_hash`, `timestamp`

Rules:

- `parent_trace_id` MUST be `null` only for a root trace entry.
- Trace ordering MUST be stable and reproducible.
- A trace entry MUST not imply execution unless paired with a matching execution result.

## ReplayRecord

Purpose: describe a replayable record of a completed trace segment.

Required fields, in order:
`replay_id`, `trace_id`, `source_hash`, `approved_effects`, `blocked_effects`, `mode`, `recorded_at`

Rules:

- Replay MUST be deterministic for the same record.
- `mode` MUST be one of `observation_only` or `effect_bearing`.

## VerificationResult

Purpose: close the action with a verification outcome.

Required fields, in order:
`verification_id`, `execution_id`, `status`, `checks`, `evidence`, `closed_at`

Rules:

- `status` MUST be one of `pass`, `fail`, or `inconclusive`.
- `checks` MUST enumerate the verification conditions used.
- A terminal action state requires exactly one closure record.

## LearningAdmissionDecision

Purpose: admit or reject knowledge for future planning.

Required fields, in order:
`admission_id`, `knowledge_id`, `status`, `reasons`, `issued_at`

Rules:

- `status` MUST be one of `admit`, `reject`, or `defer`.
- Only admitted knowledge MAY be used by planning.
- Rejected or deferred knowledge MUST NOT mutate kernel invariants.
