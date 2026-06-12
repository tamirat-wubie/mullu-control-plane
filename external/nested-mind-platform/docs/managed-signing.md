# Managed signing boundary

v7 adds a signing abstraction above the existing Ed25519 commit signature implementation.

```text
Commit
  → signable_payload()
  → local Ed25519 signer OR external signing request
  → CommitSignature
  → append-only event store
```

Supported backend states:

```text
disabled
local_ed25519
secret_manager
hsm
kms
external_request
```

Runtime configuration:

```bash
MIND_REQUIRE_SIGNATURES=true
MIND_SIGNING_BACKEND=env_ed25519
MIND_COMMIT_SIGNING_KEY_ID=root-runtime-ed25519
MIND_COMMIT_SIGNING_SEED_HEX=<32-byte-hex-seed>
```

External backends are modeled as request-completion flows:

```text
ExternalSigningRequest {
  request_id,
  key_id,
  payload_hash,
  signable_payload_hex
}
```

The live API currently requires an inline signer when `MIND_REQUIRE_SIGNATURES=true`. That prevents a mutation from being appended unsigned while external HSM/KMS integration is still incomplete.

Protected inspection endpoint:

```text
GET /system/signing/status
```

Production target:

```text
- secret manager supplies signing material or grants signing operation
- HSM/KMS signs signable payload without exposing secret key
- API attaches returned CommitSignature
- event store verifies signature before append
```

## v8 provider-shaped managed signing

v8 adds `ManagedSigningAdapter`, `ManagedSigningRequest`, and `ManagedSigningCompletion`. These types create auditable commands for AWS KMS, Google Cloud KMS, Azure Key Vault, HashiCorp Vault Transit, and PKCS#11 HSM backends. The returned signature must still verify against the commit payload before the commit may be appended.
