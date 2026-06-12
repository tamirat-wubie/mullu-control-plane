# Replication delivery and retry

v9 introduced exact-record follower ingestion. v10 adds outbound delivery receipts and retry scheduling.

```text
leader EventRecord batch
  -> ReplicationEnvelope
  -> HTTP POST follower ingest route
  -> ReplicationApplyReport
  -> synthesized ReplicationAck
  -> ReplicationDeliveryReceipt
```

## API routes

```text
POST /system/replication/follower/batches
POST /system/replication/outbound/batches
```

The follower endpoint persists leader-produced event records exactly. The outbound endpoint sends a batch to configured followers and records delivery receipts.

## Retry policy

```rust
ReplicationRetryPolicy {
    max_attempts,
    initial_delay_ms,
    max_delay_ms,
    multiplier,
}
```

Status progression:

```text
Pending
  -> Accepted
  -> RetryScheduled
  -> Exhausted
```

A delivery receipt records every attempt with status code, error text, acceptance, and timestamp.

## CLI command

```bash
cargo run -p mind-cli -- replication-push-http \
  ./data/replication-batch.json \
  /system/replication/follower/batches \
  follower-a=http://127.0.0.1:8081 \
  3
```

## Causal invariant

The follower must not recalculate sequence or hash-chain values. It verifies and stores the leader's `EventRecord` values unchanged.
