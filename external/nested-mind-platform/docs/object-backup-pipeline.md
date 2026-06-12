# Object backup pipeline

v7 adds object-backup pointers on top of the v6 backup verification model.

```text
MindBackup
  → verify backup hash/event chain/snapshots/signatures
  → write backup object
  → ObjectBackupPointer
  → reload pointer
  → verify object and backup
```

Runtime configuration:

```bash
MIND_BACKUP_OBJECT_DIR=./data/object-store
MIND_BACKUP_OBJECT_BUCKET=mind-backups
```

API endpoints:

```text
POST /system/backups/root/object
POST /system/backups/object/verify
```

CLI:

```bash
cargo run -p mind-cli -- backup-object-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  ./data/root.snapshots.jsonl \
  ./data/observability.jsonl \
  ./data/object-store \
  mind-backups \
  optional

cargo run -p mind-cli -- verify-object-backup \
  ./data/object-store \
  ./data/pointer.json \
  optional
```

The included object store is file-backed. It models the object-storage contract without adding a cloud SDK dependency. Production adapters should keep the same pointer semantics for S3, GCS, Azure Blob, or another object store.

Pointer verification checks:

```text
- object backup id equals pointer backup id
- object backup hash equals pointer backup hash
- backup manifest counts
- event hash chain
- required commit signatures when configured
- snapshot hashes
- mind id consistency
```

## v8 cloud-object plans

v8 adds provider-shaped cloud-object backup plans for S3-compatible storage, Google Cloud Storage, and Azure Blob. These plans include object keys, content hashes, provider headers, and backup verification reports. The local file-backed object backup store remains the executable local implementation.
