# Cloud object backup adapters

v8 adds cloud-object planning for S3-compatible storage, Google Cloud Storage, and Azure Blob.

```text
MindBackup
  → verify manifest/event/snapshot integrity
  → CloudObjectBackupPlan
  → provider-specific headers and object key
  → external upload
  → later object retrieval and backup verification
```

Supported providers:

```text
s3 / s3_compatible
gcs / google_cloud_storage
azure / azure_blob
```

CLI plan generation:

```bash
cargo run -p mind-cli -- cloud-backup-plan-jsonl \
  <root-mind-id> \
  ./data/root.events.jsonl \
  ./data/root.snapshots.jsonl \
  ./data/observability.jsonl \
  s3 \
  mind-backups \
  root \
  optional
```

The output contains:

```text
provider
bucket/container
object key
content hash
manifest hash
recommended provider headers
metadata
backup verification report
```

## Boundary rule

The cloud adapter does not mutate the event chain. It prepares an upload plan from an already verified backup. After upload, verification must still reload the backup object and validate its content hash and event chain.

## Remaining work

```text
- live S3/GCS/Azure SDK uploads are not implemented inside this crate
- presigned URL generation is not implemented yet
- retention/immutability lock policies are represented only as deployment responsibility
```
