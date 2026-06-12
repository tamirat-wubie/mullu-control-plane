# Contributing

## Development loop

```bash
cargo fmt --all
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## Pull request requirements

Every pull request must state:

1. Constructive delta: what capability improves.
2. Fracture delta: what risk, invariant pressure, or regression possibility is introduced.
3. Validation evidence: tests, traces, or proofs.
4. Rollback path: how to revert safely.

## Commit message style

```text
<scope>: <verb> <object>
```

Examples:

```text
core: add immutable key validation
api: expose root mind projection
ci: add clippy gate
```
