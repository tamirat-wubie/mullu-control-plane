# Meta-Reasoning Plane

Scope: all Mullu Platform modules that evaluate and adjust the platform's own reasoning processes.

Without meta-reasoning, the platform operates blindly — it does not know what it can do reliably, what is degraded, or when to escalate. The meta-reasoning plane gives the system self-knowledge.

## Purpose

Evaluate the platform's own capabilities, reliability, uncertainty, and limits to inform planning, escalation, and operator communication.

## Owned artifacts

- `CapabilityConfidence` — historical reliability score per capability.
- `UncertaintyReport` — explicit declaration of what the system does not know or cannot determine.
- `DegradedModeRecord` — record that a capability or subsystem is operating below normal reliability.
- `EscalationRecommendation` — recommendation to escalate based on self-assessment.
- `SelfHealthSnapshot` — point-in-time assessment of platform health across subsystems.

## Capability confidence rules

1. Confidence per capability MUST be derived from historical execution and verification data, not fabricated.
2. Confidence MUST track: success rate, verification pass rate, timeout rate, error rate.
3. Confidence MUST be updated after each execution/verification cycle for that capability.
4. A capability with confidence below a declared threshold MUST be flagged as degraded.
5. Confidence values MUST be in `[0.0, 1.0]`.

## Uncertainty rules

1. Uncertainty MUST be explicit. The system MUST be able to declare "I do not know X" as a typed artifact.
2. Uncertainty sources: missing evidence, low confidence, contradicted state, incomplete observation, unverified assumption.
3. Uncertainty MUST propagate: if planning depends on uncertain state, the plan carries that uncertainty.
4. Uncertainty MUST NOT be hidden from the operator surface.

## Degraded mode rules

1. Degraded mode is entered when a capability's confidence drops below its declared threshold.
2. Degraded mode MUST be recorded as a `DegradedModeRecord` with the affected capability, reason, and timestamp.
3. In degraded mode, the system MAY continue operating with reduced scope but MUST communicate the degradation.
4. Exiting degraded mode requires the capability confidence to recover above its threshold.

## Escalation recommendation rules

1. The meta-reasoning plane MAY recommend escalation when:
   - Uncertainty exceeds a threshold for a goal-critical entity.
   - A required capability is degraded.
   - Contradictions in world state remain unresolved.
   - Multiple consecutive verification failures occur.
2. Escalation recommendations MUST carry: reason, affected_ids, severity (low/medium/high/critical), suggested_action.
3. Escalation recommendations are advisory — the Governance Plane decides whether to act on them.

## Self-health snapshot rules

1. A `SelfHealthSnapshot` captures the overall health of the platform at a point in time.
2. Health dimensions: capability reliability, world-state completeness, persistence integrity, communication availability, integration availability.
3. Each dimension MUST carry a status: `healthy`, `degraded`, `unavailable`, `unknown`.
4. Snapshots MUST be deterministic — same inputs produce same health assessment.

## Policy hooks

- Confidence threshold policy: minimum confidence per capability before degraded mode triggers.
- Escalation threshold policy: when uncertainty or degradation triggers escalation.
- Self-assessment frequency: how often health snapshots are taken.

## Failure modes

- `confidence_data_unavailable` — no historical data to compute confidence for a capability.
- `health_check_failed` — a subsystem health check could not be completed.
- `escalation_channel_unavailable` — escalation recommendation cannot be delivered.

## Prohibited behaviors

- MUST NOT mutate kernel invariants (Invariant 8).
- MUST NOT bypass the learning admission gate to inject knowledge.
- MUST NOT execute adjustments without policy approval.
- MUST NOT reason about its own meta-reasoning recursively without a bounded depth limit.
- MUST NOT fabricate confidence scores without historical data.
- MUST NOT suppress uncertainty to appear more capable.

## Dependencies

- Memory Plane: historical execution/verification data for confidence computation.
- World State Plane: contradiction and confidence data.
- Communication Plane: escalation delivery.
- Governance Plane: approval for adjustments, threshold policies.
- Verification Plane: verification outcome data.
