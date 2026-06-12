# Signed-URL cloud backup adapter

v10 adds a signed-URL upload path for cloud backups:

```text
MindBackup::capture
  → verify backup hash / event chain / snapshots
  → CloudSignedUrlRequest
  → HTTP PUT signed URL
  → CloudSignedUrlReceipt
  → SQLite ledger
```

API:

```text
POST /system/backups/root/signed-url-upload
```

Request body:

```json
{
  "provider": "s3_compatible",
  "url": "https://signed-upload-url",
  "bucket": "mind-backups",
  "key": "root/backup.json"
}
```

CLI:

```bash
cargo run -p mind-cli -- cloud-backup-signed-url-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  ./data/root.snapshots.jsonl \
  ./data/observability.jsonl \
  <signed-url> \
  mind-backups \
  root/backup.json \
  s3 \
  optional
```

Signed URLs are treated as short-lived capabilities. They should be generated outside the kernel and never committed to source control.
