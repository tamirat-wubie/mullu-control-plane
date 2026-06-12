# Provider execution ledger

v11 adds provider execution requests and receipts as a common evidence envelope around SDK/gateway/cloud operations.

```text
ProviderExecutionRequest
  -> adapter
  -> command kind
  -> target
  -> payload_hash
  -> idempotency_key

ProviderExecutionReceipt
  -> execution_id
  -> expected_payload_hash
  -> observed_payload_hash
  -> status
```

This lets the platform record AWS/GCP/Azure/Vault/PKCS#11/gateway/local-mirror execution evidence without allowing provider SDK side effects to mutate the symbolic kernel directly.

## Adapter kinds

```text
aws_sdk
gcp_sdk
azure_sdk
vault_sdk
pkcs11
http_gateway
signed_url
local_mirror
```

## Command kinds

```text
kms_sign
object_put
object_get
oidc_refresh
replication_push
```

## API

```text
GET  /system/provider/execution-receipts
POST /system/provider/execution-receipts
```

## CLI

```bash
cargo run -p mind-cli -- provider-execution-receipt ./data/provider-execution-request.json same
```

The receipt is valid only when the expected hash and observed hash match for a successful execution.
