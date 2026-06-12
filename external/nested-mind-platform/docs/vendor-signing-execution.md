# Vendor signing execution boundary

v9 separates signing intent from vendor execution.

```text
ManagedSigningRequest
  → VendorSigningExecutionRequest
  → external KMS/HSM/secret-manager execution
  → VendorSigningReceipt
  → ManagedSigningCompletion
  → commit signature verification
```

The kernel never accepts a receipt as authority by itself. The returned signature still has to verify against the commit signable payload and expected public key.

## Kernel types

```text
VendorSigningExecutionRequest
VendorSigningReceipt
VendorSigningAdapterReport
```

## CLI

```bash
cargo run -p mind-cli -- vendor-signing-execution \
  ./data/managed-signing-request.json
```

The output is an auditable execution envelope with provider, key id, resource, payload hash, command, timeout, and required environment notes.

## SQLite ledger

```text
signing_execution_receipts
```

## Fracture boundary

```text
- provider SDK calls are still outside the kernel
- real attestation verification is not vendor-specific yet
- receipt storage is operational evidence, not a substitute for signature verification
```
