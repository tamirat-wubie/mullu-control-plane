# Kubernetes server dry-run executor

v22 separates the Kubernetes chaos plan from the dry-run execution request and receipt.

```text
KubernetesStagingChaosPlan
  → KubernetesDryRunExecutionRequest
  → server dry-run connector
  → KubernetesDryRunExecutionReceipt
```

## Invariants

```text
- request plan_id must match the chaos plan
- namespace must match
- manifest_count must match
- server_side=true is required for server dry-run acceptance
- receipt binds validated manifest hashes
```

## CLI

```bash
cargo run -p mind-cli -- kubernetes-dry-run-execute \
  nested-mind-staging \
  staging
```

## API

```text
GET  /system/creative-engineering/kubernetes-dry-run-executions/requests
POST /system/creative-engineering/kubernetes-dry-run-executions/requests
GET  /system/creative-engineering/kubernetes-dry-run-executions/receipts
```
