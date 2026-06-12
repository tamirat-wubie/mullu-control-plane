# Invariant Fuzzing

Invariant fuzzing generates deterministic proposal cases for the symbolic kernel. It is seed-based, reproducible, and designed to prove fail-closed behavior before production promotion.

Generated classes:

```text
empty_patch
immutable_identity_change
required_key_removal
forbidden_key_insertion
wrong_target
valid_state_expansion
projection_secret_leak_probe
```

Each generated case contains its proposal, expected acceptance class, rejection hint, and oracle.

## CLI

```bash
cargo run -p mind-cli -- invariant-fuzz-run <mind-id> 64 17
```

## API

```http
POST /system/creative-engineering/invariant-fuzz-runs
GET  /system/creative-engineering/invariant-fuzz-runs
```
