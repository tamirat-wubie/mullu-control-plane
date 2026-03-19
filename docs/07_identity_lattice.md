# Identity Lattice

Scope: all Mullu Platform modules. Every addressable entity MUST have a stable, typed identity.

Identity is the root of traceability. If an entity cannot be identified, it cannot be traced, replayed, or audited.

## Identity classes

### Platform scope

- `tenant_id` — isolates all resources under one organizational boundary.
- `workspace_id` — subdivides a tenant into distinct operational contexts.

Rules:
- `tenant_id` MUST be assigned at provisioning time and MUST NOT change.
- `workspace_id` MUST reference exactly one `tenant_id`.
- No artifact may exist without a `tenant_id` + `workspace_id` pair.

### Agent scope

- `agent_id` — uniquely identifies an agent definition across the platform.
- `session_id` — uniquely identifies one continuous interaction session of an agent.

Rules:
- `agent_id` MUST be stable across sessions and restarts.
- `session_id` MUST be unique per session instance and MUST reference one `agent_id`.
- A session MUST NOT outlive its parent agent definition.

### Goal and action scope

- `goal_id` — identifies a declared objective.
- `plan_id` — identifies a plan produced for a goal.
- `action_id` — identifies one step within a plan.
- `execution_id` — identifies one attempt to execute an action.
- `verification_id` — identifies the verification closure of an execution.

Rules:
- `goal_id` MUST be issued before any plan is created for it.
- `plan_id` MUST reference exactly one `goal_id`.
- `action_id` MUST reference exactly one `plan_id`.
- `execution_id` MUST reference exactly one `action_id`.
- `verification_id` MUST reference exactly one `execution_id`.
- This chain is strict: goal -> plan -> action -> execution -> verification. No link may be skipped.

### Persistence and audit scope

- `trace_id` — identifies one causal step in the audit trail.
- `snapshot_id` — identifies an immutable point-in-time capture of state.
- `replay_id` — identifies one replay attempt of a recorded trace segment.

Rules:
- `trace_id` MUST be unique and ordered within its session.
- `snapshot_id` MUST be content-addressed or hash-verified. Two identical snapshots MUST produce the same `snapshot_id`.
- `replay_id` MUST reference the `trace_id` range it replays.
- Replay MUST preserve all original identities from the source trace. No identity rewriting during replay.

### Integration scope

- `connector_id` — identifies a registered external system connector.
- `credential_scope_id` — identifies the permission boundary of a credential.
- `capability_id` — identifies a declared capability in the registry.

Rules:
- `connector_id` MUST be unique per external system registration.
- `credential_scope_id` MUST reference exactly one `connector_id` and MUST declare its permission boundary explicitly.
- `capability_id` MUST be unique within the capability registry snapshot.

## Issuance rules

1. Identities MUST be issued by the plane that owns the entity class. No plane may issue identities for another plane's entities.
2. Issuance MUST be recorded in the trace with the issuing plane, timestamp, and parent identity.
3. Bulk issuance MUST produce individually traceable identities. Batch IDs are not substitutes.
4. Identity format MUST include a type prefix to prevent cross-class confusion (e.g., `goal_`, `plan_`, `exec_`).

## Immutability rules

1. Once issued, an identity MUST NOT be reassigned to a different entity.
2. An identity MUST NOT be deleted. It may be marked `revoked` or `expired` but the identifier remains reserved.
3. Identity metadata (creation time, issuing plane, parent reference) MUST NOT be mutated after issuance.

## Cross-reference rules

1. Every cross-reference MUST use the full typed identity, not a shortened or aliased form.
2. Dangling references (pointing to nonexistent identities) MUST be treated as errors, not warnings.
3. Circular references are prohibited. The identity graph MUST be a directed acyclic graph within each scope chain.

## Replay and persistence identity preservation

1. Replay MUST use the original identities from the source trace. New identities MUST NOT be minted for replayed entities.
2. Persistence serialization MUST preserve the full identity including type prefix and parent chain.
3. Deserialization MUST validate identity integrity before use. Corrupted identities MUST halt processing.
4. Cross-system identity mapping (e.g., internal `connector_id` to external system ID) MUST be stored as an explicit mapping record, not as identity mutation.

## Enforcement

Any implementation that cannot resolve the full identity chain from `verification_id` back to `tenant_id` for a given action is noncompliant.
