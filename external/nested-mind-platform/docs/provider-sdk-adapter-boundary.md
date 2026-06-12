# Provider SDK Adapter Boundary

v12 adds a deterministic provider SDK invocation/receipt layer. The kernel does not directly call AWS, GCP, Azure, Vault, or PKCS#11. It records the invocation identity, command kind, target, request hash, and receipt evidence.

```text
ProviderExecutionRequest
  -> ProviderSdkInvocation
  -> ProviderSdkReceipt
  -> ProviderSdkAdapterReport
```

Supported SDK boundary labels:

```text
AwsKms
AwsS3
GcpCloudKms
Gcs
AzureKeyVault
AzureBlob
HashicorpVault
Pkcs11Hsm
HttpGateway
LocalMirror
```

The included dry-run path verifies that the receipt is bound to the invocation hash. Real SDK adapters should preserve the same receipt contract.

API routes:

```text
GET  /system/provider/sdk/receipts
POST /system/provider/sdk/dry-run
```
