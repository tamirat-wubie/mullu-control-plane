# Backup and Restore

Backups are verified data artifacts, not live mutations.

```text
event records
  + snapshots
  + trace events
  + audit events
  → MindBackup
  → backup_hash
  → verification report
```

## API

```text
POST /system/backups/root
POST /system/backups/verify
GET  /system/backups/manifests
```

The root backup endpoint returns a full backup object. In SQLite mode, the backup manifest is also written into `backup_manifests`.

## Verification

Backup verification checks:

```text
- backup hash
- manifest counts
- event hash chain
- commit signatures when required
- snapshot hash
- snapshot state hash
- snapshot lawbook hash
- mind-id consistency
```

## CLI

```bash
cargo run -p mind-cli -- backup-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  ./data/root.snapshots.jsonl \
  ./data/observability.jsonl \
  ./data/root.backup.json \
  optional

cargo run -p mind-cli -- verify-backup ./data/root.backup.json optional

cargo run -p mind-cli -- restore-backup-jsonl \
  ./data/root.backup.json \
  ./restore/root.events.jsonl \
  ./restore/root.snapshots.jsonl \
  ./restore/observability.jsonl \
  optional
```

Restore defaults to `NewFilesOnly`. Existing target files cause rejection. This prevents accidental overwrite of a live append-only chain.

## Production posture

```text
- Store backup files outside the application volume.
- Verify backups before retention or restore.
- Keep signing keys separate from backup artifacts.
- Do not restore directly into a live runtime without stopping the service and auditing the target chain.
```

## v7 object backup pipeline

The v7 file-backed object store models cloud-object semantics without adding a vendor SDK. Configure:

```bash
MIND_BACKUP_OBJECT_DIR=./data/object-store
MIND_BACKUP_OBJECT_BUCKET=mind-backups
```

API:

```text
POST /system/backups/root/object
POST /system/backups/object/verify
```

CLI:

```bash
cargo run -p mind-cli -- backup-object-jsonl <root-mind-id> events.jsonl snapshots.jsonl observability.jsonl ./data/object-store mind-backups optional
cargo run -p mind-cli -- verify-object-backup ./data/object-store pointer.json optional
```

The pointer is not trusted by itself. Verification reloads the object and re-runs backup verification.
