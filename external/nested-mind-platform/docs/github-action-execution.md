# GitHub action execution boundary

v22 connects GitHub App token evidence to action execution evidence for:

```text
- check-run writes
- branch-protection reconciliation
```

```text
GitHubAppInstallationTokenPlan
  + GitHubCheckRunWritePlan | BranchProtectionReconcilePlan
  → GitHubActionExecutionPlan
  + GitHubAppInstallationTokenReceipt
  → GitHubActionExecutionReceipt
```

## Invariants

```text
- token plan repository must match action repository
- execution receipt must bind token_receipt_id
- live execution can only be marked executed when status code is 2xx
- dry-run action receipts are explicit and cannot masquerade as live writes
```

## API

```text
GET  /system/github/action-execution/plans
POST /system/github/action-execution/plans
GET  /system/github/action-execution/receipts
POST /system/github/action-execution/receipts
```

## CLI

```bash
cargo run -p mind-cli -- github-action-execution-plan \
  mullusi/nested-mind-platform \
  demo-head-sha
```
