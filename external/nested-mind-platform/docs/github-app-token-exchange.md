# GitHub App token exchange

v22 adds a GitHub App installation-token exchange boundary.

```text
GitHubAppInstallationTokenRequest
  → GitHubAppInstallationTokenPlan
  → connector exchange
  → GitHubAppInstallationTokenReceipt
  → SQLite ledger
```

The kernel does not store raw installation tokens. Receipts store only a token fingerprint, permissions, expiry, response hash, and request/plan binding.

## Invariants

```text
- app_id and installation_id must be non-zero
- repository and private-key fingerprint must be present
- token TTL must be 1..=3600 seconds
- issued receipts must include token_fingerprint
- receipt hash binds plan_id + request_id + installation_id + status + expiry
```

## CLI

```bash
cargo run -p mind-cli -- github-app-token-plan \
  mullusi/nested-mind-platform \
  12345 \
  67890 \
  private-key-fingerprint
```

## API

```text
GET  /system/github/app/installation-token-plans
POST /system/github/app/installation-token-plans
GET  /system/github/app/installation-token-receipts
POST /system/github/app/installation-token-receipts
```
