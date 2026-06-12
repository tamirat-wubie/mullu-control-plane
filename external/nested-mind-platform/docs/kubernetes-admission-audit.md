# Kubernetes admission and audit capture

v22 added Kubernetes server dry-run receipts. v23 adds admission/audit evidence:

```text
KubernetesDryRunExecutionRequest
  → KubernetesDryRunExecutionReceipt
  → KubernetesAdmissionAuditRequest
  → KubernetesAdmissionAuditReceipt
  → KubernetesAdmissionAuditReport
```

The default policy requires:

```text
server dry-run evidence
audit uid
nested.mind/rehearsal annotation
```

This makes live staging chaos promotion depend on admission/audit evidence rather than only CLI output.
