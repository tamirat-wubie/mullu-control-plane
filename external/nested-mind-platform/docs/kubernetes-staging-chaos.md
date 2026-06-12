# Kubernetes staging chaos execution

v21 adds a Kubernetes-shaped staging chaos execution contract.

```text
ChaosRehearsalPlan
  → KubernetesStagingChaosPlan
  → kubectl apply --dry-run=server or approved live apply
  → KubernetesStagingChaosReceipt
```

The plan renders one Kubernetes Job manifest per chaos experiment and enforces a staging namespace guard. Live mode requires an approval certificate hash before the plan is accepted.

Execution modes:

```text
plan_only       client-side planning only
server_dry_run  server admission / validation rehearsal
live_approved   live staging submission with approval certificate
```

Receipts record manifest hashes, observed signals, dry-run status, and whether live side effects were expected.
