# Managed KMS/HSM signing adapters

v8 adds provider-shaped managed signing requests for the commit-signing boundary.

```text
Commit
  → signable_payload
  → ManagedSigningRequest
  → provider command
  → external KMS/HSM/Vault operation
  → ManagedSigningCompletion
  → CommitSignature
  → verify before append
```

Supported provider command shapes:

```text
aws_kms
cloud_kms / gcp_cloud_kms
azure_key_vault
hashicorp_vault
pkcs11_hsm
```

The kernel does not store private key material. It accepts a completion only when:

```text
request_id matches
commit_id matches
key_id matches
provider matches
payload_hash matches
public_key_hex matches configured key descriptor
returned signature verifies the commit payload
```

CLI request generation:

```bash
cargo run -p mind-cli -- managed-signing-request \
  ./data/commit.json \
  aws_kms \
  root-runtime-ed25519 \
  arn:aws:kms:us-east-1:111122223333:key/demo \
  <ed25519-public-key-hex>
```

## Boundary rule

A managed signing adapter may prepare provider-specific commands, but the append-only event store only accepts the resulting commit after the commit signature validates cryptographically.

## Remaining work

```text
- vendor SDK invocation is not wired into the API process
- key rotation workflows are not implemented yet
- attestation policy is simple and should become provider-specific
```
