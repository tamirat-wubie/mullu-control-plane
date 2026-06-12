# Connector execution worker

v23 adds a connector-worker plan/receipt layer for side-effecting jobs.

```text
ScheduledJob
  → ConnectorWorkerJobPlan
  → external connector execution
  → ConnectorWorkerExecutionReceipt
```

Supported action kinds:

```text
github_action_execution
branch_protection_worker
kubernetes_dry_run_execution
waiver_notification_delivery
oidc_refresh
replication_delivery
cloud_backup_upload
provider_execution
```

Approved execution requires an external receipt hash. This prevents the worker from claiming that a side effect happened without provider evidence.
