# Live secret connector workers

v24 adds a live secret connector evidence layer.

```text
SecretAccessPlan
  → live connector request template
  → provider-side secret read
  → SecretAccessReceipt
  → LiveSecretConnectorReceipt
```

The kernel records fingerprints and response hashes only. It does not persist raw secret material, private keys, or provider response bodies.

## Invariants

```text
+ access plan hash must verify
+ connector plan hash must verify
+ connector receipt must bind access receipt id
+ resolved receipts must include material_fingerprint
+ backend in connector receipt must match backend in secret access receipt
```

## Objects

```text
LiveSecretConnectorPlan
LiveSecretConnectorReceipt
LiveSecretConnectorMode
LiveSecretConnectorStatus
```

## SQLite ledgers

```text
live_secret_connector_plans
live_secret_connector_receipts
```
