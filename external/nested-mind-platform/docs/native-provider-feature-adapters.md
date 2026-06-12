# Native provider feature adapters

v14 adds an explicit native provider adapter registry.

```text
ProviderSdkFeatureMatrix
  → NativeProviderAdapterRegistry
  → NativeProviderAdapterReport
```

Feature flags:

```text
provider-aws-kms
provider-aws-s3
provider-gcp-kms
provider-gcs
provider-azure-key-vault
provider-azure-blob
provider-vault
provider-pkcs11
provider-http-gateway
provider-local-mirror
```

The registry answers whether a provider command is disabled, dry-run only, external-gateway based, or compiled as a native feature. The report remains deterministic and does not itself call cloud/HSM APIs. Real provider calls must satisfy the existing `ProviderExecutionReceipt` / `ProviderSdkReceipt` contract.

Feature propagation is wired through `mind-api`, `mind-cli`, `mind-worker`, and `mind-connectors` into `mind-core`, so a provider feature can be enabled at the binary crate boundary while the kernel still records a deterministic capability report.

Example:

```bash
cargo run -p mind-api --features provider-local-mirror
cargo run -p mind-cli --features provider-local-mirror -- native-provider-adapters
```
