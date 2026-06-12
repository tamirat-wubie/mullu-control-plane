# Validation status

The repository includes Rust tests for the kernel, event store, snapshots, schema migrations, observability, backup/restore, identity/signing/object backup, v8 direct-identity/managed-signing/cloud/replication seams, and v9 discovery/execution/transfer/follower-ingest/consensus seams, and v10 live-connector/governance ledgers.

Run in a Rust-enabled environment:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

Current execution limitation for this generated artifact:

```text
Cargo is not installed in the generation environment, so the Rust test suite could not be executed here.
```

Static checks performed during generation:

```text
- Rust file brace-balance scan
- required v9/v10 module/export presence
- package path integrity before zipping
```

## v9 validation additions

New tests cover:

```text
+ OIDC discovery document validation and JWKS cache creation
+ vendor signing receipt conversion into managed signing completion
+ local cloud mirror upload/download verification
+ durable follower ingestion preserving leader record hashes
+ consensus quorum and election tally
+ SQLite v9 ledgers for cache, cloud transfer, replication inbox, and consensus membership
```

The repository still needs to be validated in a Rust-enabled environment with:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```


## v10 validation additions

New tests cover:

```text
+ live OIDC refresh report construction from discovery document + JWKS
+ replication retry policy delay calculation
+ governed consensus change proposal and verifiable judgment
+ signed-URL backup request/receipt hashing
+ SQLite v10 ledgers for live refreshes, signed-URL receipts, replication delivery receipts, and consensus change judgments
```


## v10 validation status

The v10 package includes tests for live OIDC refresh report construction, retry policy delay capping, signed URL receipt verification, governed consensus changes, and SQLite v10 ledger persistence. Cargo was not available in the packaging environment, so the Rust test suite must be run after extraction.


## v11 added test targets

```text
crates/mind-core/tests/v11_scheduler_provider_consensus_commit.rs
crates/mind-store-sqlite/tests/sqlite_v11_ledgers.rs
```

Coverage intent:

```text
+ scheduled job due/claim/success trace
+ provider execution receipt verification
+ consensus commit certificate quorum verification
+ SQLite v11 scheduler/provider/consensus certificate ledgers
```

## v12 added test targets

```text
crates/mind-core/tests/v12_worker_sdk_consensus_apply.rs
crates/mind-store-sqlite/tests/sqlite_v12_ledgers.rs
```

Coverage intent:

```text
+ scheduler lease claim reports
+ worker runtime run-once reports
+ provider SDK dry-run receipt verification
+ consensus-certified replication batch apply to follower store
+ SQLite v12 ledgers for leases, worker runs, provider SDK receipts, and consensus apply reports
```


## v13 added test targets

```text
crates/mind-core/tests/v13_worker_daemon_provider_consensus.rs
crates/mind-store-sqlite/tests/sqlite_v13_ledgers.rs
```

Coverage intent:

```text
+ worker daemon tick construction from lease claims
+ provider SDK conservative feature matrix
+ consensus apply idempotency reapply/conflict detection
+ consensus log compaction retention decisions
+ SQLite v13 ledgers and database-backed scheduler claims
```

Validation to run in a Rust-enabled environment:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```


## v14 added test targets

```text
crates/mind-core/tests/v14_receipts_native_compaction_leases.rs
crates/mind-store-sqlite/tests/sqlite_v14_ledgers.rs
```

Coverage intent:

```text
+ job execution receipt creation and verification
+ distributed lease request/receipt verification
+ native provider adapter registry and evaluation
+ backup-guarded physical consensus compaction planning
+ SQLite v14 ledgers and physical consensus certificate deletion path
```

Validation should run with:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## v15 validation status

Static checks performed in this environment:

```text
+ TOML parse validation
+ Rust brace/bracket/parenthesis balance scan
+ required v15 module/export/API/schema symbols present
+ package ZIP integrity
```

Cargo/rustc are not installed in this environment, so the Rust suite still needs to be run after extraction:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## v16 validation status

Static package checks were performed in the generation environment. Full Rust validation still requires:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

v16 added tests covering live domain job reports, distributed lease execution receipts, provider SDK execution policy, and consensus retention approval certificates.

## v17 validation status

Added static artifacts and tests for:

```text
+ creative engineering suggestion ranking
+ chaos rehearsal plan hash verification
+ deterministic invariant fuzz case generation
+ production readiness gate blocking logic
+ SQLite v17 ledgers
```

The Rust test suite still needs to be executed in a Rust-enabled environment.

## v18 validation additions

Added static/test coverage intent for:

```text
+ deterministic chaos execution run verification
+ invariant fuzz harness execution against EvolutionEngine
+ readiness waiver proposal/certificate/application workflow
+ creative engineering suggestions converted into scheduled jobs
+ SQLite v18 ledgers
```

Cargo/rustc availability still determines whether the full suite can be executed in the target environment.

## v19 validation status

Static package checks were run in the generation environment. Rust compilation and tests still need a Rust-enabled environment.

Recommended commands:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo test -p mind-core --test v19_enforced_readiness_engineering
cargo test -p mind-store-sqlite --test sqlite_v19_ledgers
```

## v20 validation notes

Static package checks should verify:

```text
+ GitHub evidence bundle hash verification
+ branch protection policy/evaluation hash verification
+ live staging chaos adapter plan/receipt verification
+ waiver review certificate verification
+ SQLite v20 ledger migrations
```

Run in a Rust-enabled environment:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## v21 validation status

Static package checks cover TOML parsing, rough Rust delimiter balance, required module/export/API/schema symbol presence, and ZIP integrity. The Rust compiler/test suite still must be run in a Rust-enabled environment.

## v22 validation status

Static checks were run in the artifact environment:

```text
+ TOML parse validation
+ Rust brace/bracket/parenthesis balance scan
+ required v22 module/export/API/schema symbols present
+ ZIP integrity
```

Cargo and rustc were unavailable in the artifact environment, so the Rust test suite must be run after extraction.


## v23 validation status

Static artifact checks were prepared for:

```text
secret manager JWT modules
connector worker modules
Kubernetes admission/audit modules
waiver notification adapter modules
SQLite v23 ledger symbols
```

Cargo/rustc execution still depends on a Rust-enabled environment.

## v24 validation status

Static additions:

```text
+ live secret connector plan/receipt module
+ GitHub token exchange worker module
+ Kubernetes audit-log collector module
+ notification delivery client module
+ SQLite schema migration 24
```

The Rust test suite must still be run in a Rust-enabled environment.

## v25 validation status

Static checks were performed for:

```text
required v25 modules
required v25 API route strings
required SQLite migration/table names
TOML parse validation
Rust delimiter balance scan
ZIP package integrity
```

Cargo and rustc are unavailable in this environment, so workspace tests still need to run in a Rust-enabled environment.
