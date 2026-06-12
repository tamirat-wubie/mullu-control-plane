# Leader replication protocol

v8 adds an explicit leader/follower replication protocol skeleton.

```text
leader event records
  → follower cursor
  → ReplicationBatch
  → follower verifies sequence/hash/signatures
  → ReplicationAck
  → leader quorum report
```

Core types:

```text
ReplicationCursor
ReplicationTerm
ReplicationBatch
ReplicationAck
ReplicationQuorumReport
LeaderReplicationProtocol
FollowerReplicationProtocol
```

Follower validation checks:

```text
- batch mind_id equals cursor mind_id
- batch from_sequence equals cursor next_sequence
- previous_record_hash equals cursor previous_record_hash
- every record belongs to the same mind
- event sequence has no gap
- record hash chain is continuous
- required commit signatures verify when enabled
- batch hash matches the batch body
```

CLI preview:

```bash
cargo run -p mind-cli -- replication-batch-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  leader-a \
  1 \
  none \
  optional
```

## Boundary rule

This is a replication protocol skeleton, not a distributed consensus system. It can validate batches and acknowledgements but does not yet implement transport, durable follower append, leader election, or consensus membership changes.
