# GitHub check-run writer

v21 adds a hash-bound GitHub check-run write boundary.

```text
readiness evidence
  → GitHubCheckRunWritePlan
  → GitHub App installation token / checks:write boundary
  → GitHubCheckRunWriteReceipt
  → ledger
```

The kernel does not call GitHub directly. It creates a deterministic REST endpoint and payload, then records a receipt containing the GitHub check-run id, response hash, mode, and endpoint evidence.

Modes:

```text
plan_only       produces no external side effect
dry_run         validates the request and records accepted intent
write_approved  requires an external GitHub App execution receipt
```

The write path is intentionally GitHub-App-shaped because GitHub check-run creation is not a generic user/OAuth operation.
