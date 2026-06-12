# Distributed Lease Adapters

v15 adds a concrete adapter registry above the v14 lease boundary.

```text
DistributedLeaseServiceBoundary
  → DistributedLeaseAdapterRegistry
  → DistributedLeaseAdapterReport
  → DistributedLeaseClaimReceipt
```

Implemented adapter status:

| Backend | Mode | Production status |
|---|---|---|
| SQLite compare-and-swap | local compare-and-swap | ready for single SQLite writer |
| Postgres advisory lock | native client boundary | implementation pending |
| Redis Redlock | native client boundary | safety review required |
| etcd lease | native client boundary | implementation pending |
| Consul session | native client boundary | implementation pending |
| External HTTP gateway | gateway boundary | requires receipt-producing gateway |

The adapter report records whether the claim was accepted, rejected, or delegated to an external boundary. Fencing token requirements remain explicit.

## API

```text
GET  /system/scheduler/distributed-lease/adapters
POST /system/scheduler/distributed-lease/adapters/evaluate
```

## CLI

```bash
cargo run -p mind-cli -- distributed-lease-adapters
cargo run -p mind-cli -- distributed-lease-adapter-evaluate ./data/job.json worker-a sqlite 60
```
