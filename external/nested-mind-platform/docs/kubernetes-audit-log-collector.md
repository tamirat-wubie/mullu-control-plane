# Kubernetes audit-log collector

v24 extends admission/audit capture into a collector model that can track audit-log watermarks.

```text
KubernetesAdmissionAuditReport
  → KubernetesAuditLogCollectorPlan
  → audit source collection
  → KubernetesAuditLogCollectorReport
```

The collector binds admission evidence to audit UIDs and a new collection watermark. This lets staging chaos promotion depend on both server-dry-run evidence and audit-log evidence.

## Invariants

```text
+ collector plan binds admission report id
+ collected report must include audit UID evidence
+ failures move report to rejected
+ missing admission audit maps to missing collector status
```

## SQLite ledgers

```text
kubernetes_audit_log_collector_plans
kubernetes_audit_log_collector_reports
```
