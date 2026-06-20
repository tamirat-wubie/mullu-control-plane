# World State Plane

> **In one box:** The system's structured model of "what is currently true in
> the world" — the agent's map of reality that it reasons over before acting.
> This page defines how that model is maintained and queried. One-sentence
> version: [world-state plane](GLOSSARY.md#world-state-plane).
> *(Doc type: Reference.)*

Scope: all Mullu Platform modules that maintain or query the canonical representation of the current environment.

Without a world-state plane, the platform treats observations as isolated evidence fragments. The world-state plane turns typed evidence into situational understanding — entities, dependencies, contradictions, and confidence.

## Purpose

Maintain the canonical, queryable representation of the current environment state.

## Owned artifacts

- `StateEntity` — a named, typed object in the world model (file, process, service, resource).
- `EntityRelation` — a directed dependency or association between entities.
- `StateSnapshot` — a point-in-time capture of the full entity graph.
- `ContradictionRecord` — an explicit record of conflicting evidence about the same entity.
- `ConfidenceAnnotation` — a confidence score attached to an entity or relation.

## Entity rules

1. Every entity MUST carry a stable `entity_id` and an explicit `entity_type`.
2. Entity state MUST be derived from evidence. Entities MUST NOT be fabricated without observation.
3. Entity metadata MUST track the evidence source(s) that established the entity.
4. Entity removal requires explicit evidence of absence, not timeout or assumption.

## Relation rules

1. Relations MUST be directed: `source_entity_id` -> `target_entity_id` with an explicit `relation_type`.
2. Relations MUST reference existing entities. Dangling references are errors.
3. Relation types MUST be drawn from a declared vocabulary (e.g., `depends_on`, `contains`, `produces`, `consumes`).
4. Circular dependencies MUST be detected and flagged, not silently accepted.

## Snapshot rules

1. A `StateSnapshot` MUST capture all entities and relations at a point in time.
2. Snapshots MUST be immutable after creation.
3. Snapshot identity MUST include a content hash for comparison.
4. Two identical world states MUST produce the same snapshot hash.

## Contradiction handling

1. When multiple evidence sources disagree about the same entity attribute, a `ContradictionRecord` MUST be created.
2. Contradictions MUST NOT be silently resolved by picking one source. Resolution requires explicit strategy.
3. Contradiction resolution strategies: `prefer_latest`, `prefer_highest_confidence`, `escalate`, `manual`.
4. Unresolved contradictions MUST be visible to the planning and operator surfaces.

## Confidence rules

1. Confidence is a value in `[0.0, 1.0]` attached to an entity, relation, or attribute.
2. Confidence of `1.0` means verified by the Verification Plane.
3. Confidence of `0.0` means no supporting evidence.
4. Confidence MUST NOT be fabricated. It MUST derive from evidence quality and verification status.
5. Confidence propagation: if entity A depends on entity B, A's effective confidence MUST NOT exceed B's confidence.

## Temporal state

1. Entity state changes over time MUST be tracked as a sequence of state versions.
2. Each version MUST carry a timestamp and the evidence that caused the change.
3. Historical state MUST be queryable — the world-state plane is not only the current snapshot.

## Policy hooks

- State mutation policy: what evidence quality is required to establish or update an entity.
- Contradiction escalation policy: when contradictions trigger operator notification.
- Confidence threshold policy: minimum confidence for entities to be used in planning.

## Failure modes

- `entity_not_found` — queried entity does not exist in the current state.
- `dangling_relation` — relation references a nonexistent entity.
- `circular_dependency` — dependency graph contains a cycle.
- `contradiction_unresolved` — conflicting evidence without explicit resolution.
- `confidence_below_threshold` — entity confidence too low for requested use.
- `snapshot_corrupted` — snapshot integrity check failed.

## Prohibited behaviors

- MUST NOT generate observations (that is the Perception Plane's role).
- MUST NOT plan or decide (that is the Planning Plane's role).
- MUST NOT hold stale state without expiry markers.
- MUST NOT silently resolve contradictions.
- MUST NOT fabricate entities without evidence.

## Dependencies

- Perception Plane: structured observations as input.
- Verification Plane: verification status feeds confidence.
- Memory Plane: historical state versions stored as episodic memory.
- Persistence: snapshots MUST survive process restarts.

## Repository Observation Projection

Repository observation packets enter the World State Plane through:

```text
project_repository_observation_packet_to_world_state(packet, store)
```

Projection rules:

1. The packet creates repository and worktree entities.
2. The packet creates a directed `repository_has_worktree` relation.
3. The packet creates claims for observation mode, freshness state, proof state,
   planning admission, and repository digest refs.
4. The packet creates a projection event that binds entities, relation, claims,
   solver outcome, and live evidence state.
5. Fresh live packets with `ProofState Pass` can expose planning claims.
6. Foundation packets and failed live packets remain blocked from planning.
7. Failed live packets create an open contradiction instead of silently choosing
   a usable state.
8. No projected repository observation claim is allowed for execution.

The focused verification lane is:

```powershell
python -m pytest tests/test_gateway/test_world_state.py::test_repository_observation_packet_projects_to_world_state_planning_claims tests/test_gateway/test_world_state.py::test_repository_observation_command_failure_projects_open_contradiction tests/test_gateway/test_world_state.py::test_foundation_repository_observation_projection_blocks_without_contradiction -q
```

STATUS:
  Completeness: 100%
  Invariants verified: repository observation packet projection, expiry binding, contradiction visibility, planning-only admission, execution denial
  Open issues: provider and connector observation projections remain future proof threads
  Next action: bind admitted repository world-state projections into ProblemStar evidence input
