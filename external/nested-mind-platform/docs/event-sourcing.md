# Event Sourcing

The platform treats state as replayable consequence, not as the primary source of truth.

```text
Ι + H → replay → Σ
```

`Ι` is the immutable mind identity. `H` is the ordered event stream. `Σ` is the reconstructed symbolic state.

## Record structure

Each accepted commit is wrapped in an `EventRecord`:

```text
EventRecord := {
  sequence,
  mind_id,
  commit_id,
  previous_record_hash,
  record_hash,
  commit
}
```

The record hash commits to the sequence number, mind id, commit id, previous record hash, and commit body. This creates a per-mind hash chain.

## Commit structure

Each `Commit` contains:

```text
id
proposal_id
mind_id
parent_commit
actor
reason
at
patch
topology
lawbook_transition
before_hash
after_hash
judgment
signature
```

`topology` carries replayable child-mind changes.
`lawbook_transition` carries replayable Λ migration.
`signature` can be required by the event store before append.

The commit proves a state transition. The record proves stream ordering.

## Safe mutation order

The API applies this order:

```text
proposal
  → evaluate against current mind
  → create EvolutionPlan
  → sign commit when configured
  → append plan.commit to event store
  → apply plan to live memory
```

If the append fails, the state is not mutated.

## Replay checks

Replay rejects the stream when any condition fails:

```text
record sequence gap
record previous hash mismatch
record hash mismatch
signature missing when required
invalid commit signature
commit target mismatch
commit parent mismatch
commit before_hash mismatch
commit after_hash mismatch
lawbook transition hash mismatch
lawbook rejection on reconstructed next state
invariant rejection on reconstructed patch
topology rejection, such as wrong parent or duplicate child
```

## Storage modes

The kernel includes:

```text
InMemoryEventStore
JsonlEventStore
SqliteEventStore
```

The snapshot layer adds:

```text
InMemorySnapshotStore
JsonlSnapshotStore
SqliteEventStore as SnapshotStore
```

## Topology effects

A commit may include topology effects. The initial effect is:

```text
AttachChild { identity }
```

Child attachment also writes registry cells into the parent state, so replay reconstructs both the visible symbolic registry and the in-memory child map.
