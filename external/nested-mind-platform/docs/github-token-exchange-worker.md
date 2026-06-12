# GitHub token exchange worker

v24 separates GitHub App JWT signing evidence from installation-token exchange evidence.

```text
SecretAccessReceipt
  → GitHubAppJwtReceipt
  → LiveSecretConnectorReceipt
  → GitHubAppInstallationTokenReceipt
  → GitHubTokenExchangeWorkerReceipt
```

The token exchange worker stores token fingerprints, expiry evidence, permission hashes, and response hashes. It does not store raw GitHub App JWTs or installation access tokens.

## Invariants

```text
+ GitHub JWT receipt must verify
+ secret connector receipt must verify
+ installation id must match the exchange plan
+ issued-token status requires token_fingerprint
+ exchange receipt must bind installation-token receipt id
```

## SQLite ledgers

```text
github_token_exchange_worker_plans
github_token_exchange_worker_receipts
```
