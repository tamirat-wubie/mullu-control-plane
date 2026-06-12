# Branch-protection reconcile worker

v21 generated branch-protection reconcile plans and receipts. v22 adds a worker-level plan/report so reconcile operations can be scheduled, grouped, executed, and audited.

```text
BranchProtectionReconcilePlan[]
  → BranchProtectionWorkerPlan
  → BranchProtectionReconcileReceipt[]
  → BranchProtectionWorkerReport
```

## Status model

```text
planned
no_drift
applied
rejected
```

A worker report is rejected if any attached reconcile receipt is rejected.

## CLI

```bash
cargo run -p mind-cli -- branch-protection-worker \
  mullusi/nested-mind-platform \
  main
```

## API

```text
GET  /system/github/branch-protection/worker-plans
POST /system/github/branch-protection/worker-plans
GET  /system/github/branch-protection/worker-reports
POST /system/github/branch-protection/worker-reports
```
