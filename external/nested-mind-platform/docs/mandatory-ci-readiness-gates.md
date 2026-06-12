# Mandatory CI readiness gates

v19 adds a CI-level readiness object that aggregates normal Rust checks with executable readiness evidence.

```text
cargo fmt
cargo clippy
cargo test
executable readiness tests
chaos execution
invariant fuzz execution
staging chaos report
production readiness gate
  → MandatoryCiGateReport
```

The gate fails when required checks are missing or failed, invariant fuzz failures exceed policy, the production readiness gate is blocked, or staging chaos evidence is required but not attached.

This object is designed for GitHub branch protection: CI should upload the JSON report and fail the workflow if `status != passed`.
