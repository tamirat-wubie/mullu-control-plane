# Provider SDK feature matrix

The v13 provider matrix makes native SDK readiness explicit instead of implicit.

Default state:

```text
AWS KMS/S3               disabled
GCP KMS/GCS              disabled
Azure Key Vault/Blob     disabled
Vault                    disabled
PKCS#11                  disabled
HTTP gateway             external gateway
Local mirror             dry-run/local
```

The matrix is exposed by:

```text
GET /system/provider/sdk/features
```

and by:

```bash
cargo run -p mind-cli -- provider-sdk-features
```

Native SDK feature flags are declared in `mind-connectors`, but they intentionally do not pull vendor crates yet. The next safe step is to add one provider at a time behind its feature flag and require receipt verification before marking scheduled work succeeded.
