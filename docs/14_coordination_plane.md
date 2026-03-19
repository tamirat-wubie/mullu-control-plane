# Coordination Plane

Scope: all Mullu Platform modules that orchestrate work across multiple agents, roles, or human participants.

Without coordination, each agent operates in isolation. The coordination plane gives the system collaboration — delegation, handoff, merge, conflict resolution, and provenance-preserving multi-party workflows.

## Purpose

Orchestrate multi-agent and multi-step workflows with explicit delegation, handoff, and conflict resolution.

## Owned artifacts

- `DelegationRequest` — a request to assign work to another agent or role.
- `DelegationResult` — the outcome of a delegation attempt.
- `HandoffRecord` — a provenance-preserving transfer of responsibility between parties.
- `MergeDecision` — the outcome of combining results from multiple sources.
- `ConflictRecord` — an explicit record of conflicting results or decisions.

## Delegation rules

1. Delegation MUST name the target agent or role explicitly. Implicit routing is prohibited.
2. The delegating party MUST NOT assign work to agents lacking the required capabilities.
3. Delegation MUST carry the full identity chain: goal_id, delegator_id, delegate_id, action scope.
4. A delegation result MUST be one of: `accepted`, `rejected`, `expired`.
5. Rejected delegations MUST carry explicit reasons.

## Handoff rules

1. A handoff transfers responsibility from one party to another. Both parties MUST be recorded.
2. Handoffs MUST preserve the full provenance chain — the receiving party inherits the identity context.
3. A handoff MUST NOT silently drop pending verifications or open execution closures.
4. Handoff timing MUST be explicit — the transfer moment is recorded as a timestamp.

## Merge rules

1. When multiple sources produce results for the same goal, a merge decision MUST be explicit.
2. Merge MUST NOT silently discard conflicting results. All inputs MUST be recorded.
3. Merge outcome MUST be one of: `merged`, `conflict_detected`, `deferred`.
4. A merged result MUST reference all source result IDs.

## Conflict resolution rules

1. Conflicts MUST be recorded as `ConflictRecord` with all conflicting artifact IDs.
2. Conflict resolution strategy MUST be explicit: `prefer_latest`, `prefer_highest_confidence`, `escalate`, `manual`.
3. Automatic conflict resolution MUST NOT override policy decisions.
4. Unresolved conflicts MUST be escalated (via the Communication Plane) rather than silently dropped.

## Provenance preservation

1. Every coordination artifact MUST carry the identity of the originator and all participants.
2. Coordination MUST NOT rewrite or erase provenance from delegated or handed-off work.
3. The full coordination chain MUST be traceable: who delegated to whom, who handed off to whom, what was merged.

## Policy hooks

- Delegation policy: which agents may delegate to which roles, with what scope limits.
- Handoff policy: conditions under which handoff is permitted (e.g., verification must be closed first).
- Merge policy: which merge strategies are permitted for which artifact types.
- Escalation policy: when unresolved conflicts trigger escalation.

## Failure modes

- `delegate_not_found` — target agent or role does not exist.
- `delegate_lacks_capability` — target lacks required capabilities for the work.
- `delegation_expired` — delegate did not respond within the deadline.
- `handoff_incomplete` — handoff attempted with open verifications or pending executions.
- `merge_conflict` — conflicting results that cannot be automatically resolved.
- `provenance_broken` — coordination chain has a missing or unresolvable identity reference.

## Prohibited behaviors

- MUST NOT override individual agent policy decisions.
- MUST NOT assign work to agents lacking required capabilities.
- MUST NOT hide coordination failures from the trace.
- MUST NOT silently discard conflicting results.
- MUST NOT rewrite provenance.

## Dependencies

- Capability Plane: agent capabilities determine delegation eligibility.
- Governance Plane: coordination policy, delegation limits.
- Communication Plane: escalation of unresolved conflicts.
- Temporal Plane: delegation deadlines, handoff timing.
- Planning Plane: workflow plans that drive coordination.
