# Durable follower replication

v9 adds a hash-preserving follower ingestion path.

## Why this path exists

Leader append and follower ingestion are different operations:

```text
leader append:
  Commit → EventRecord::new(sequence, previous_hash, commit)

follower ingest:
  EventRecord[] → verify tail continuity → persist exact records
```

A follower must not call the normal leader append path for replicated records, because doing so could recalculate sequence or record hashes and fork causal history.

## Kernel traits

```text
AppendOnlyEventStore
ReplicatedEventStore
```

## Ingestion checks

```text
+ all replicated records belong to one mind
+ first sequence equals local cursor.next_sequence
+ first previous_record_hash equals local cursor.previous_record_hash
+ each record hash recalculates exactly
+ each commit signature verifies when signatures are required
+ records are persisted exactly as leader-produced records
```

## API

```text
GET  /system/replication/transport
POST /system/replication/follower/batches
```

## CLI

```bash
cargo run -p mind-cli -- replication-ingest-jsonl \
  ./data/follower.events.jsonl \
  ./data/replication-batch.json \
  optional \
  ./data/replication-inbox.jsonl
```

## Fracture boundary

```text
- outbound HTTP push/retry scheduling is not implemented yet
- follower state replay/apply after ingest is not automatic yet
- no consensus-backed leader selection yet
```
