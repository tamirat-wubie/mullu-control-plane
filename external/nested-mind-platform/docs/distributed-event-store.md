# Distributed event-store strategy

v7 adds an explicit strategy model for event-store deployment posture. It does not implement consensus yet; it prevents unsafe local writes when the node is configured as a follower/archive node.

```text
DistributedEventStorePlan {
  strategy,
  node_id,
  role,
  voting_members,
  quorum_size,
  allow_local_appends,
  replication_lag_limit_events
}
```

Strategies:

```text
single_writer              one writable node
leader_replicated          leader appends; followers replicate
consensus_replicated       future quorum-backed append path
object_archived_follower   read/archive node; never appends locally
```

Runtime configuration:

```bash
MIND_EVENT_STORE_STRATEGY=single_writer
MIND_NODE_ID=local
MIND_NODE_ROLE=single
MIND_VOTING_MEMBERS=1
MIND_QUORUM_SIZE=1
MIND_ALLOW_LOCAL_APPENDS=true
```

Protected inspection endpoint:

```text
GET /system/distributed-plan
```

Mutation endpoints call:

```text
DistributedEventStorePlan::validate_append_authority()
```

before creating an append. A follower or object-archive node rejects local mutation before evaluation/signing/append.

Next target:

```text
- leader forwarding
- replicated event-log tailing
- compare-and-swap append tokens
- quorum certification
- snapshot distribution
```

## v8 leader/follower replication protocol

v8 adds `ReplicationCursor`, `ReplicationTerm`, `ReplicationBatch`, `ReplicationAck`, and quorum reports. A follower accepts a batch only when sequence continuity, previous-record hash continuity, record hashes, and signature requirements are satisfied.
