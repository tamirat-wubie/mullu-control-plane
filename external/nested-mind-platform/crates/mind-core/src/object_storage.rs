use crate::{
    hash_serializable, BackupVerificationReport, EventId, MindBackup, MindError, MindId,
    MindResult, SignatureRequirement,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ObjectStorageBackend {
    LocalFilesystem,
    S3Compatible,
    Gcs,
    AzureBlob,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectStorageLocation {
    pub backend: ObjectStorageBackend,
    pub bucket: String,
    pub key: String,
    pub uri: String,
    pub bytes: usize,
    pub sha256_hex: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub etag: Option<String>,
    pub written_at: OffsetDateTime,
}

pub trait ObjectStore {
    fn put_object(
        &mut self,
        bucket: &str,
        key: &str,
        body: &[u8],
    ) -> MindResult<ObjectStorageLocation>;
    fn get_object(&self, bucket: &str, key: &str) -> MindResult<Vec<u8>>;
    fn list_prefix(&self, bucket: &str, prefix: &str) -> MindResult<Vec<ObjectStorageLocation>>;
}

#[derive(Clone, Debug)]
pub struct FilesystemObjectStore {
    root: PathBuf,
}

impl FilesystemObjectStore {
    pub fn new(root: impl Into<PathBuf>) -> MindResult<Self> {
        let root = root.into();
        fs::create_dir_all(&root)?;
        Ok(Self { root })
    }

    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    fn path_for(&self, bucket: &str, key: &str) -> MindResult<PathBuf> {
        validate_object_component(bucket, "bucket")?;
        validate_object_key(key)?;
        Ok(self.root.join(bucket).join(key))
    }

    fn location_for(&self, bucket: &str, key: &str, body: &[u8]) -> ObjectStorageLocation {
        let sha256_hex = sha256_hex(body);
        ObjectStorageLocation {
            backend: ObjectStorageBackend::LocalFilesystem,
            bucket: bucket.to_owned(),
            key: key.to_owned(),
            uri: format!("file://{}/{}/{}", self.root.display(), bucket, key),
            bytes: body.len(),
            etag: Some(sha256_hex.clone()),
            sha256_hex,
            written_at: OffsetDateTime::now_utc(),
        }
    }
}

impl ObjectStore for FilesystemObjectStore {
    fn put_object(
        &mut self,
        bucket: &str,
        key: &str,
        body: &[u8],
    ) -> MindResult<ObjectStorageLocation> {
        let path = self.path_for(bucket, key)?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let temporary = path.with_extension("upload.tmp");
        fs::write(&temporary, body)?;
        fs::rename(&temporary, &path)?;
        Ok(self.location_for(bucket, key, body))
    }

    fn get_object(&self, bucket: &str, key: &str) -> MindResult<Vec<u8>> {
        let path = self.path_for(bucket, key)?;
        if !path.exists() {
            return Err(MindError::ObjectNotFound {
                bucket: bucket.to_owned(),
                key: key.to_owned(),
            });
        }
        Ok(fs::read(path)?)
    }

    fn list_prefix(&self, bucket: &str, prefix: &str) -> MindResult<Vec<ObjectStorageLocation>> {
        validate_object_component(bucket, "bucket")?;
        validate_object_key(prefix)?;
        let bucket_root = self.root.join(bucket);
        if !bucket_root.exists() {
            return Ok(Vec::new());
        }
        let mut locations = Vec::new();
        collect_locations(&bucket_root, &bucket_root, bucket, prefix, &mut locations)?;
        locations.sort_by(|a, b| a.key.cmp(&b.key));
        Ok(locations)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BackupObjectReceipt {
    pub receipt_id: EventId,
    pub backup_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    pub manifest_hash: String,
    pub location: ObjectStorageLocation,
    pub verification: BackupVerificationReport,
}

#[derive(Clone, Debug, Default)]
pub struct BackupObjectPipeline;

impl BackupObjectPipeline {
    pub fn write_backup<S: ObjectStore>(
        store: &mut S,
        bucket: &str,
        key_prefix: &str,
        backup: &MindBackup,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<BackupObjectReceipt> {
        let verification = backup.verify(signature_requirement)?;
        let body = serde_json::to_vec_pretty(backup)?;
        let prefix = normalized_prefix(key_prefix)?;
        let key = format!("{}{}.backup.json", prefix, backup.manifest.backup_id);
        let location = store.put_object(bucket, &key, &body)?;
        Ok(BackupObjectReceipt {
            receipt_id: EventId::new(),
            backup_id: backup.manifest.backup_id,
            mind_id: backup.manifest.mind_id,
            manifest_hash: hash_serializable(&backup.manifest)?,
            location,
            verification,
        })
    }

    pub fn read_backup<S: ObjectStore>(
        store: &S,
        bucket: &str,
        key: &str,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<(MindBackup, BackupVerificationReport)> {
        let body = store.get_object(bucket, key)?;
        let backup = serde_json::from_slice::<MindBackup>(&body)?;
        let report = backup.verify(signature_requirement)?;
        Ok((backup, report))
    }
}

fn normalized_prefix(prefix: &str) -> MindResult<String> {
    if prefix.trim().is_empty() {
        return Ok(String::new());
    }
    validate_object_key(prefix)?;
    Ok(prefix.trim_matches('/').to_owned() + "/")
}

fn validate_object_component(value: &str, label: &str) -> MindResult<()> {
    if value.trim().is_empty() {
        return Err(MindError::ObjectStorage {
            reason: format!("{label} is empty"),
        });
    }
    if value.contains("..") || value.contains('/') || value.contains('\\') {
        return Err(MindError::ObjectStorage {
            reason: format!("{label} contains unsafe path characters"),
        });
    }
    Ok(())
}

fn validate_object_key(value: &str) -> MindResult<()> {
    if value.contains("..") || value.contains('\\') || value.starts_with('/') {
        return Err(MindError::ObjectStorage {
            reason: "object key contains unsafe path characters".to_owned(),
        });
    }
    Ok(())
}

fn collect_locations(
    root: &Path,
    current: &Path,
    bucket: &str,
    prefix: &str,
    locations: &mut Vec<ObjectStorageLocation>,
) -> MindResult<()> {
    for entry in fs::read_dir(current)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            collect_locations(root, &path, bucket, prefix, locations)?;
            continue;
        }
        let Ok(relative) = path.strip_prefix(root) else {
            continue;
        };
        let key = relative.to_string_lossy().replace('\\', "/");
        if !key.starts_with(prefix.trim_matches('/')) {
            continue;
        }
        let body = fs::read(&path)?;
        locations.push(ObjectStorageLocation {
            backend: ObjectStorageBackend::LocalFilesystem,
            bucket: bucket.to_owned(),
            key: key.clone(),
            uri: format!(
                "file://{}/{}/{}",
                root.parent().unwrap_or(root).display(),
                bucket,
                key
            ),
            bytes: body.len(),
            sha256_hex: sha256_hex(&body),
            etag: None,
            written_at: OffsetDateTime::now_utc(),
        });
    }
    Ok(())
}

fn sha256_hex(body: &[u8]) -> String {
    let digest = Sha256::digest(body);
    hex::encode(digest)
}
