# Native Provider Execution Receipts

v15 connects native provider capability evaluation to receipt production.

```text
ProviderExecutionRequest
  → NativeProviderAdapterRegistry
  → NativeProviderAdapterReport
  → ProviderSdkInvocation
  → ProviderSdkReceipt
  → ProviderExecutionReceipt
  → NativeProviderExecutionReceipt
```

The receipt binds:

```text
execution_id
sdk
command_kind
target
request_hash
provider receipt
SDK receipt
adapter mode
```

Dry-run execution remains explicit. A dry-run-capable provider is not treated as live production execution unless the caller allows dry-run mode.

## API

```text
GET  /system/provider/native-executions
POST /system/provider/native-executions/execute
```

## CLI

```bash
cargo run -p mind-cli -- native-provider-execute ./data/provider-execution-request.json dry-run
```
