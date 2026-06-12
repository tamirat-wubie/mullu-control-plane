# Snapshot compaction

Snapshot compaction prevents unbounded snapshot growth without weakening replayability.

Policy:

```text
keep_latest: number of newest snapshots to preserve
min_events_between_snapshots: event distance before a new snapshot is due
```

The compaction decision returns:

```text
keep_snapshot_ids
remove_snapshot_ids
should_create_snapshot
reasons
```

Supported stores:

```text
+ InMemorySnapshotStore
+ JsonlSnapshotStore through rewrite-on-compaction
+ SqliteEventStore through DELETE by snapshot_id
```

API:

```text
POST /minds/root/snapshots/compact
```

Environment:

```bash
export MIND_SNAPSHOT_KEEP_LATEST=3
export MIND_SNAPSHOT_MIN_EVENTS_BETWEEN=25
```
