# Secret-backed GitHub App JWT

v23 separates GitHub App JWT creation into two auditable steps:

```text
SecretReference
  → SecretAccessPlan
  → SecretAccessReceipt
  → GitHubAppJwtPlan
  → GitHubAppJwtReceipt
```

The kernel never stores the private key or JWT body. It stores fingerprints, versions, plan hashes, and receipt hashes.

Supported secret backends are represented as deterministic boundaries:

```text
environment
kubernetes_secret
aws_secrets_manager
gcp_secret_manager
azure_key_vault
hashicorp_vault
external_gateway
```

Production rule: runtime connector workers may resolve a secret only when an approved plan exists and the receipt fingerprint matches the expected key fingerprint when one is configured.
