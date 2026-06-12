# Provider SDK execution policy

v16 introduces a provider SDK execution policy layer.

```text
ProviderExecutionRequest
  → ProviderSpecificSdkExecutionPlan
  → NativeProviderExecutionReceipt
  → ProviderSdkExecutionReport
```

Policies:

```text
plan_only                  construct invocation without trusting execution
dry_run_allowed             allow local/dry-run receipt generation
native_feature_required    require compiled native provider feature
external_receipt_required  require gateway/provider receipt boundary
```

The provider SDK execution report records the selected SDK, command kind, request hash, native receipt, provider receipt, and acceptance status.

## Runtime endpoint

```text
GET  /system/provider/sdk/executions
POST /system/provider/sdk/executions
```

## CLI

```bash
cargo run -p mind-cli -- provider-sdk-execute ./data/provider-execution-request.json plan
cargo run -p mind-cli -- provider-sdk-execute ./data/provider-execution-request.json dry-run
cargo run -p mind-cli -- provider-sdk-execute ./data/provider-execution-request.json native
cargo run -p mind-cli -- provider-sdk-execute ./data/provider-execution-request.json gateway
```

## Boundary rule

The symbolic kernel accepts only hash-bound execution reports. Vendor SDKs may be added behind feature flags, but each live SDK call must return the same receipt contract used by dry-run and gateway execution.
