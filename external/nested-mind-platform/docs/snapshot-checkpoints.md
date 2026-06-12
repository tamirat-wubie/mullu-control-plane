# Snapshot Checkpoints

Snapshots are checkpoint records for faster recovery and bounded replay.

```text
EventRecord[1..N]
  → Mind
  → SnapshotRecord(after_sequence=N, after_record_hash=hash(N))
  → tail replay from N+1
```

A snapshot captures:

```text
identity
lawbook
state
children
history
```

The record also stores integrity hashes:

```text
state_hash
lawbook_hash
snapshot_hash
```

`SnapshotRecord::verify` checks that:

```text
calculated snapshot hash equals stored snapshot_hash
calculated state hash equals state_hash
calculated lawbook hash equals lawbook_hash
```

## Stores

The scaffold includes:

```text
InMemorySnapshotStore
JsonlSnapshotStore
SqliteEventStore as SnapshotStore
```

JSONL is suitable for local development. SQLite is the transactional single-node path in this scaffold.
