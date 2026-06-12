# Cloud transfer execution

v8 produced cloud-object backup plans. v9 adds an executable local mirror transfer adapter.

```text
MindBackup
  → CloudObjectBackupPlan
  → CloudUploadExecutionRequest
  → LocalCloudMirrorStore::put_backup
  → CloudUploadReceipt
  → LocalCloudMirrorStore::load_backup
  → CloudDownloadReceipt
```

The local mirror adapter writes backup bodies into a provider/bucket/key directory layout and verifies body hashes and backup integrity on both upload and download.

## API

```text
POST /system/backups/root/cloud-mirror
```

## CLI

```bash
cargo run -p mind-cli -- cloud-backup-upload-mirror-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  ./data/root.snapshots.jsonl \
  ./data/observability.jsonl \
  s3 \
  mind-backups \
  root \
  ./data/cloud-mirror \
  optional
```

## Environment

```bash
MIND_CLOUD_OBJECT_MIRROR_DIR=./data/cloud-mirror
MIND_CLOUD_BACKUP_PROVIDER=s3
MIND_CLOUD_BACKUP_BUCKET=mind-backups
MIND_CLOUD_BACKUP_PREFIX=root
```

## Fracture boundary

```text
- S3/GCS/Azure SDK upload execution is not implemented yet
- local mirror receipts model the transfer boundary and verification semantics
- object storage credentials are intentionally outside this kernel layer
```
