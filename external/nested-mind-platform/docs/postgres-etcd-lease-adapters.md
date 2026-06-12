# Postgres and etcd lease adapter execution contracts

v16 adds execution receipts for distributed scheduler lease backends.

```text
ScheduledJob
  → DistributedLeaseServiceBoundary
  → backend-specific operation plan
  → DistributedLeaseAdapterReport
  → DistributedLeaseClaimReceipt
  → DistributedLeaseExecutionReceipt
```

Supported execution plans:

```text
SQLite compare-and-swap       implemented local claim path
Postgres advisory lock        SQL operation contract + receipt boundary
etcd transaction lease        compare/put operation contract + receipt boundary
external HTTP gateway         external receipt boundary
```

The Postgres and etcd paths are represented as deterministic command plans plus receipts. This lets a later live adapter execute the plan without changing the scheduler's symbolic contract.

## Runtime endpoint

```text
GET  /system/scheduler/distributed-lease/executions
POST /system/scheduler/distributed-lease/executions
```

## CLI

```bash
cargo run -p mind-cli -- distributed-lease-execute ./data/job.json worker-a sqlite 60 sqlite
cargo run -p mind-cli -- distributed-lease-execute ./data/job.json worker-a postgres 60 postgres
cargo run -p mind-cli -- distributed-lease-execute ./data/job.json worker-a etcd 60 etcd
```

## Safety rule

A lease execution receipt must bind the job id, worker id, backend, expected payload hash, and fencing token. If a receipt does not bind those values, the platform must reject it.
