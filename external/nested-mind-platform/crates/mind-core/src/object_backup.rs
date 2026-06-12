use crate::{
    BackupVerificationReport, EventId, MindBackup, MindError, MindId, MindResult,
    SignatureRequirement,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectStorageLocation {
    pub provider: String,
    pub bucket: String,
    pub key: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub version_id: Option<String>,
}

impl ObjectStorageLocation {
    #[must_use]
    pub fn filesystem(
        bucket: impl Into<String>,
        key: impl Into<String>,
        endpoint: impl Into<String>,
    ) -> Self {
        Self {
            provider: "filesystem".to_owned(),
            bucket: bucket.into(),
            key: key.into(),
            endpoint: Some(endpoint.into()),
            version_id: None,
        }
    }

    #[must_use]
    pub fn object_uri(&self) -> String {
        match &self.endpoint {
            Some(endpoint) => format!(
                "{}://{}/{}?endpoint={}",
                self.provider, self.bucket, self.key, endpoint
            ),
            None => format!("{}://{}/{}", self.provider, self.bucket, self.key),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectBackupPointer {
    pub object_id: EventId,
    pub location: ObjectStorageLocation,
    pub backup_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    pub backup_hash: String,
    pub content_hash: String,
    pub size_bytes: u64,
    pub created_at: OffsetDateTime,
}

impl ObjectBackupPointer {
    #[must_use]
    pub fn key(&self) -> &str {
        &self.location.key
    }

    #[must_use]
    pub fn bucket(&self) -> &str {
        &self.location.bucket
    }
}

pub type BackupObjectLocation = ObjectStorageLocation;
pub type BackupObjectRef = ObjectBackupPointer;
pub type BackupObjectVerificationReport = BackupVerificationReport;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BackupEncryptionMode {
    None,
    ServerManaged,
    CustomerManaged,
    ExternalEnvelope,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectBackupTarget {
    pub provider: String,
    pub bucket: String,
    pub key_prefix: String,
    pub encryption: BackupEncryptionMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
}

impl ObjectBackupTarget {
    #[must_use]
    pub fn filesystem(bucket: impl Into<String>, key_prefix: impl Into<String>) -> Self {
        Self {
            provider: "filesystem".to_owned(),
            bucket: bucket.into(),
            key_prefix: key_prefix.into(),
            encryption: BackupEncryptionMode::None,
            endpoint: None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectBackupPlan {
    pub mind_id: Option<MindId>,
    pub target: ObjectBackupTarget,
    pub signature_requirement: SignatureRequirement,
    pub include_observability: bool,
}

impl ObjectBackupPlan {
    #[must_use]
    pub fn new(
        mind_id: Option<MindId>,
        target: ObjectBackupTarget,
        signature_requirement: SignatureRequirement,
    ) -> Self {
        Self {
            mind_id,
            target,
            signature_requirement,
            include_observability: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectBackupReplicationReport {
    pub pointer: ObjectBackupPointer,
    pub verification: BackupVerificationReport,
    pub content_hash_valid: bool,
}

#[derive(Clone, Debug)]
pub struct FileObjectBackupStore {
    root: PathBuf,
}

impl FileObjectBackupStore {
    pub fn new(root: impl AsRef<Path>) -> MindResult<Self> {
        let root = root.as_ref().to_path_buf();
        fs::create_dir_all(&root)?;
        Ok(Self { root })
    }

    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn put_backup(
        &self,
        bucket: impl AsRef<str>,
        key: impl AsRef<str>,
        backup: &MindBackup,
    ) -> MindResult<ObjectBackupPointer> {
        let bucket = sanitize_bucket(bucket.as_ref())?;
        let key = sanitize_key(key.as_ref())?;
        let path = self.path_for(&bucket, &key)?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let bytes = serde_json::to_vec_pretty(backup)?;
        let content_hash = sha256_hex(&bytes);
        let temporary_path = path.with_extension("backup.tmp");
        {
            let mut file = OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(true)
                .open(&temporary_path)?;
            file.write_all(&bytes)?;
            file.write_all(b"\n")?;
            file.flush()?;
            file.sync_data()?;
        }
        fs::rename(&temporary_path, &path)?;
        let metadata = fs::metadata(&path)?;
        Ok(ObjectBackupPointer {
            object_id: EventId::new(),
            location: ObjectStorageLocation::filesystem(
                bucket,
                key,
                self.root.display().to_string(),
            ),
            backup_id: backup.manifest.backup_id,
            mind_id: backup.manifest.mind_id,
            backup_hash: backup.manifest.backup_hash.clone(),
            content_hash,
            size_bytes: metadata.len(),
            created_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn put_verified_backup(
        &self,
        bucket: impl AsRef<str>,
        key: impl AsRef<str>,
        backup: &MindBackup,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<ObjectBackupPointer> {
        backup.verify(signature_requirement)?;
        self.put_backup(bucket, key, backup)
    }

    pub fn load_backup(
        &self,
        bucket: impl AsRef<str>,
        key: impl AsRef<str>,
    ) -> MindResult<MindBackup> {
        let bucket = sanitize_bucket(bucket.as_ref())?;
        let key = sanitize_key(key.as_ref())?;
        let path = self.path_for(&bucket, &key)?;
        if !path.exists() {
            return Err(MindError::ObjectNotFound { bucket, key });
        }
        let file = OpenOptions::new().read(true).open(path)?;
        Ok(serde_json::from_reader::<_, MindBackup>(file)?)
    }

    pub fn load_pointer(&self, pointer: &ObjectBackupPointer) -> MindResult<MindBackup> {
        self.load_backup(pointer.bucket(), pointer.key())
    }

    pub fn verify_pointer(
        &self,
        pointer: &ObjectBackupPointer,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<BackupVerificationReport> {
        let bucket = sanitize_bucket(pointer.bucket())?;
        let key = sanitize_key(pointer.key())?;
        let path = self.path_for(&bucket, &key)?;
        if !path.exists() {
            return Err(MindError::ObjectNotFound { bucket, key });
        }

        let mut bytes = Vec::new();
        OpenOptions::new()
            .read(true)
            .open(&path)?
            .read_to_end(&mut bytes)?;
        while bytes
            .last()
            .is_some_and(|byte| *byte == b'\n' || *byte == b'\r')
        {
            bytes.pop();
        }
        let actual_content_hash = sha256_hex(&bytes);
        if actual_content_hash != pointer.content_hash {
            return Err(MindError::ObjectBackupHashMismatch {
                expected: pointer.content_hash.clone(),
                actual: actual_content_hash,
            });
        }
        let backup: MindBackup = serde_json::from_slice(&bytes)?;
        if backup.manifest.backup_id != pointer.backup_id {
            return Err(MindError::ObjectBackupFailed {
                reason: "object backup id does not match pointer".to_owned(),
            });
        }
        if backup.manifest.backup_hash != pointer.backup_hash {
            return Err(MindError::ObjectBackupHashMismatch {
                expected: pointer.backup_hash.clone(),
                actual: backup.manifest.backup_hash.clone(),
            });
        }
        backup.verify(signature_requirement)
    }

    pub fn replicate_and_verify(
        &self,
        bucket: impl AsRef<str>,
        key: impl AsRef<str>,
        backup: &MindBackup,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<ObjectBackupReplicationReport> {
        let pointer = self.put_verified_backup(bucket, key, backup, signature_requirement)?;
        let verification = self.verify_pointer(&pointer, signature_requirement)?;
        Ok(ObjectBackupReplicationReport {
            pointer,
            verification,
            content_hash_valid: true,
        })
    }

    pub fn list_keys(&self, bucket: impl AsRef<str>) -> MindResult<Vec<String>> {
        let bucket = sanitize_bucket(bucket.as_ref())?;
        let base = self.root.join(&bucket);
        if !base.exists() {
            return Ok(Vec::new());
        }
        let mut keys = Vec::new();
        collect_json_keys(&base, &base, &mut keys)?;
        keys.sort();
        Ok(keys)
    }

    fn path_for(&self, bucket: &str, key: &str) -> MindResult<PathBuf> {
        if key.trim().is_empty()
            || key.contains("..")
            || key.starts_with('/')
            || key.starts_with('\\')
        {
            return Err(MindError::ObjectBackupLocationInvalid(format!(
                "unsafe object key `{key}`"
            )));
        }
        Ok(self.root.join(bucket).join(key))
    }
}

fn sanitize_bucket(bucket: &str) -> MindResult<String> {
    let bucket = bucket.trim().trim_matches('/').replace('\\', "/");
    if bucket.is_empty() || bucket.contains("..") || bucket.contains('/') {
        return Err(MindError::ObjectBackupLocationInvalid(
            "unsafe object bucket".to_owned(),
        ));
    }
    Ok(bucket)
}

fn sanitize_key(key: &str) -> MindResult<String> {
    let key = key.trim().trim_start_matches('/').replace('\\', "/");
    if key.is_empty() || key.contains("..") || key.starts_with('/') {
        return Err(MindError::ObjectBackupLocationInvalid(format!(
            "unsafe object key `{key}`"
        )));
    }
    Ok(key)
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

fn collect_json_keys(base: &Path, current: &Path, keys: &mut Vec<String>) -> MindResult<()> {
    for entry in fs::read_dir(current)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            collect_json_keys(base, &path, keys)?;
        } else if path
            .extension()
            .is_some_and(|extension| extension.to_string_lossy() == "json")
        {
            let relative =
                path.strip_prefix(base)
                    .map_err(|error| MindError::ObjectBackupFailed {
                        reason: error.to_string(),
                    })?;
            keys.push(relative.to_string_lossy().replace('\\', "/"));
        }
    }
    Ok(())
}
