# Live staging chaos adapter boundary

v20 keeps destructive staging chaos behind an explicit adapter plan and receipt contract.

```text
ChaosRehearsalPlan
  + optional StagingChaosRunReport
  + adapter backend
  + execution mode
  → LiveStagingChaosAdapterPlan
  → LiveStagingChaosAdapterReceipt
```

Backends:

```text
kubernetes_server_dry_run
argo_rollout_analysis
http_gateway
manual_runbook
```

Modes:

```text
plan_only
server_dry_run
live_approved
```

The included execution path is still receipt-producing and non-destructive. Kubernetes mode emits `kubectl ... --dry-run=server` style commands so staging admission/validation can be rehearsed before live mutation.

CLI:

```bash
cargo run -p mind-cli -- live-chaos-adapter-plan \
  ./data/chaos-plan.json \
  none \
  kubernetes \
  dry-run
```

API:

```text
GET  /system/creative-engineering/live-staging-chaos-adapters
POST /system/creative-engineering/live-staging-chaos-adapters
GET  /system/creative-engineering/live-staging-chaos-adapters/receipts
POST /system/creative-engineering/live-staging-chaos-adapters/receipts
```
