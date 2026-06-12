# Live connector adapters

v10 adds a separate connector crate so network and provider side effects remain outside the symbolic kernel.

```text
kernel object
  -> connector request
  -> external HTTP/provider boundary
  -> receipt/report
  -> SQLite or JSONL ledger
```

## Crate

```text
crates/mind-connectors
```

The connector crate depends on `mind-core` types and emits only deterministic reports already defined by the kernel.

## Live OIDC discovery/JWKS refresh

```text
OidcDiscoveryConfig
  -> LiveOidcRefreshRequest
  -> GET /.well-known/openid-configuration
  -> GET jwks_uri
  -> LiveOidcRefreshReport
  -> OidcJwksCacheEntry
```

The API route is:

```text
POST /system/oidc-verifier/refresh-live
```

The CLI command is:

```bash
cargo run -p mind-cli -- oidc-live-refresh \
  https://issuer.example \
  nested-mind-api \
  RS256
```

## Signing gateway

v10 keeps vendor-specific KMS/HSM execution at a gateway boundary. The kernel prepares a `VendorSigningExecutionRequest`; the gateway returns a `VendorSigningReceipt` with signature evidence.

```text
ManagedSigningRequest
  -> VendorSigningExecutionRequest
  -> external signing gateway
  -> VendorSigningReceipt
  -> ManagedSigningCompletion
```

The connector crate includes an HTTP signing gateway client. Direct in-process vendor SDK calls are intentionally not part of the kernel.

## Signed URL backup upload

```text
MindBackup
  -> CloudSignedUrlRequest
  -> HTTP PUT signed URL
  -> CloudSignedUrlReceipt
```

The API route is:

```text
POST /system/backups/root/signed-url-upload
```

The CLI command is:

```bash
cargo run -p mind-cli -- cloud-backup-signed-url-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  ./data/root.snapshots.jsonl \
  ./data/observability.jsonl \
  '<signed-url>' \
  mind-backups \
  root/backup.json \
  s3 \
  optional
```

## Governance invariant

Connectors may perform side effects, but they cannot mutate symbolic mind state directly. They return evidence objects. The API or CLI then records those evidence objects in an append/audit ledger.
