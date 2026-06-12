# Outbound replication transport and retry receipts

v9 added exact-record follower ingestion. v10 adds outbound HTTP push and retry evidence.

```text
ReplicationBatch
  → ReplicationEnvelope
  → POST follower endpoint
  → ReplicationAck
  → ReplicationDeliveryReceipt
  → retry or finish
```

API:

```text
POST /system/replication/outbound/batches
```

Runtime config:

```bash
MIND_REPLICATION_FOLLOWERS=node-b=http://node-b:8080,node-c=http://node-c:8080
MIND_REPLICATION_RETRY_MAX_ATTEMPTS=3
MIND_REPLICATION_RETRY_INITIAL_DELAY_MS=250
MIND_REPLICATION_RETRY_MAX_DELAY_MS=5000
MIND_REPLICATION_RETRY_MULTIPLIER=2
MIND_REPLICATION_BEARER_TOKEN=
```

CLI:

```bash
cargo run -p mind-cli -- replication-push-http \
  ./data/replication-batch.json \
  /system/replication/follower/batches \
  node-b=http://node-b:8080,node-c=http://node-c:8080 \
  3
```

The delivery receipt is not the commit itself. It is adapter evidence describing attempts, status codes, acceptance, and final acknowledgement.
