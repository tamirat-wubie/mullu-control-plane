use crate::{
    CloudObjectBackupPlan, CloudObjectProvider, EventId, MindBackup, MindError, MindResult,
    SignatureRequirement,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CloudTransferMode {
    PlanOnly,
    LocalMirror,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudUploadExecutionRequest {
    pub execution_id: EventId,
    pub provider: CloudObjectProvider,
    pub bucket: String,
    pub key: String,
    pub object_uri: String,
    pub body_sha256_hex: String,
    pub body_bytes: usize,
    pub mode: CloudTransferMode,
    pub created_at: OffsetDateTime,
}

impl CloudUploadExecutionRequest {
    #[must_use]
    pub fn from_plan(plan: &CloudObjectBackupPlan, mode: CloudTransferMode) -> Self {
        Self {
            execution_id: EventId::new(),
            provider: plan.put_request.provider,
            bucket: plan.put_request.bucket.clone(),
            key: plan.put_request.key.clone(),
            object_uri: cloud_object_uri(
                plan.put_request.provider,
                &plan.put_request.bucket,
                &plan.put_request.key,
            ),
            body_sha256_hex: plan.put_request.body_sha256_hex.clone(),
            body_bytes: plan.put_request.body_bytes,
            mode,
            created_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudUploadReceipt {
    pub receipt_id: EventId,
    pub execution_id: EventId,
    pub provider: CloudObjectProvider,
    pub bucket: String,
    pub key: String,
    pub object_uri: String,
    pub body_sha256_hex: String,
    pub body_bytes: usize,
    pub uploaded_at: OffsetDateTime,
    pub verified: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudDownloadReceipt {
    pub receipt_id: EventId,
    pub upload_receipt_id: EventId,
    pub object_uri: String,
    pub body_sha256_hex: String,
    pub body_bytes: usize,
    pub downloaded_at: OffsetDateTime,
    pub verified: bool,
}

#[derive(Clone, Debug)]
pub struct LocalCloudMirrorStore {
    root: PathBuf,
}

impl LocalCloudMirrorStore {
    pub fn new(root: impl Into<PathBuf>) -> MindResult<Self> {
        let root = root.into();
        fs::create_dir_all(&root)?;
        Ok(Self { root })
    }

    pub fn put_backup(
        &self,
        plan: &CloudObjectBackupPlan,
        backup: &MindBackup,
        requirement: SignatureRequirement,
    ) -> MindResult<CloudUploadReceipt> {
        backup.verify(requirement)?;
        if plan.backup_id != backup.manifest.backup_id {
            return Err(MindError::ObjectStorage {
                reason: "cloud upload plan does not match backup id".to_owned(),
            });
        }
        let body = serde_json::to_vec(backup)?;
        let actual_hash = sha256_hex(&body);
        if actual_hash != plan.put_request.body_sha256_hex {
            return Err(MindError::ObjectBackupHashMismatch {
                expected: plan.put_request.body_sha256_hex.clone(),
                actual: actual_hash,
            });
        }
        let path = self.path_for(
            plan.put_request.provider,
            &plan.put_request.bucket,
            &plan.put_request.key,
        )?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, &body)?;
        Ok(CloudUploadReceipt {
            receipt_id: EventId::new(),
            execution_id: EventId::new(),
            provider: plan.put_request.provider,
            bucket: plan.put_request.bucket.clone(),
            key: plan.put_request.key.clone(),
            object_uri: cloud_object_uri(
                plan.put_request.provider,
                &plan.put_request.bucket,
                &plan.put_request.key,
            ),
            body_sha256_hex: plan.put_request.body_sha256_hex.clone(),
            body_bytes: body.len(),
            uploaded_at: OffsetDateTime::now_utc(),
            verified: true,
        })
    }

    pub fn load_backup(
        &self,
        receipt: &CloudUploadReceipt,
        requirement: SignatureRequirement,
    ) -> MindResult<(MindBackup, CloudDownloadReceipt)> {
        let path = self.path_for(receipt.provider, &receipt.bucket, &receipt.key)?;
        if !path.exists() {
            return Err(MindError::ObjectNotFound {
                bucket: receipt.bucket.clone(),
                key: receipt.key.clone(),
            });
        }
        let body = fs::read(&path)?;
        let actual_hash = sha256_hex(&body);
        if actual_hash != receipt.body_sha256_hex {
            return Err(MindError::ObjectBackupHashMismatch {
                expected: receipt.body_sha256_hex.clone(),
                actual: actual_hash,
            });
        }
        let backup = serde_json::from_slice::<MindBackup>(&body)?;
        backup.verify(requirement)?;
        let download = CloudDownloadReceipt {
            receipt_id: EventId::new(),
            upload_receipt_id: receipt.receipt_id,
            object_uri: receipt.object_uri.clone(),
            body_sha256_hex: receipt.body_sha256_hex.clone(),
            body_bytes: body.len(),
            downloaded_at: OffsetDateTime::now_utc(),
            verified: true,
        };
        Ok((backup, download))
    }

    fn path_for(
        &self,
        provider: CloudObjectProvider,
        bucket: &str,
        key: &str,
    ) -> MindResult<PathBuf> {
        if bucket.trim().is_empty()
            || key.trim().is_empty()
            || key.contains("..")
            || key.starts_with('/')
            || key.contains('\\')
        {
            return Err(MindError::ObjectStorage {
                reason: "unsafe cloud mirror bucket/key".to_owned(),
            });
        }
        Ok(self
            .root
            .join(format!("{:?}", provider).to_ascii_lowercase())
            .join(sanitize_component(bucket))
            .join(Path::new(key)))
    }
}

#[must_use]
pub fn cloud_object_uri(provider: CloudObjectProvider, bucket: &str, key: &str) -> String {
    match provider {
        CloudObjectProvider::S3Compatible => format!("s3://{bucket}/{key}"),
        CloudObjectProvider::Gcs => format!("gs://{bucket}/{key}"),
        CloudObjectProvider::AzureBlob => format!("azure-blob://{bucket}/{key}"),
    }
}

fn sanitize_component(value: &str) -> String {
    value
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.') {
                c
            } else {
                '_'
            }
        })
        .collect()
}

fn sha256_hex(body: &[u8]) -> String {
    hex::encode(Sha256::digest(body))
}
