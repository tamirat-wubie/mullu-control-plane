# Replay Audit

Replay audit verifies that H reconstructs Σ and Λ without hidden mutation.

## Full audit

```text
Identity + EventRecord[]
  → verify event chain
  → verify signatures when required
  → replay commits
  → report final hash and latest commit
```

## Snapshot audit

```text
SnapshotRecord + EventRecord tail
  → verify snapshot
  → verify tail begins at snapshot.after_sequence + 1
  → verify tail previous hash equals snapshot.after_record_hash
  → replay only tail
```

Audit output includes:

```text
mind_id
mode
event_count
passed
signature_requirement
final_hash
latest_commit_id
snapshot_id
failure
```

The CLI exposes:

```bash
cargo run -p mind-cli -- audit-jsonl <root-mind-id> <event-log.jsonl> [required|optional]
cargo run -p mind-cli -- snapshot-jsonl <root-mind-id> <event-log.jsonl> <snapshot-log.jsonl> [required|optional]
```
