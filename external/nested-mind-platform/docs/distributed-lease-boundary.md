# Distributed lease boundary

v14 adds a boundary contract for scheduler leases outside one SQLite process.

```text
ScheduledJob
  → DistributedLeaseClaimRequest
  → external or local lease service
  → DistributedLeaseClaimReceipt
```

Supported boundary kinds:

```text
sqlite_compare_and_swap
postgres_advisory_lock
redis_redlock
etcd_lease
consul_session
external_http_gateway
```

The receipt binds job id, worker id, expected payload hash, observed payload hash, backend kind, lease expiry, and optional fencing token. This prepares the scheduler for multi-worker deployments without letting a lease service mutate symbolic state directly.
