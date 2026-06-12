use crate::{
    hash_serializable, BackupVerificationReport, EventId, MindBackup, MindError, MindResult,
    ObjectStorageBackend, SignatureRequirement,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum CloudObjectProvider {
    S3Compatible,
    Gcs,
    AzureBlob,
}

impl CloudObjectProvider {
    #[must_use]
    pub fn backend(self) -> ObjectStorageBackend {
        match self {
            Self::S3Compatible => ObjectStorageBackend::S3Compatible,
            Self::Gcs => ObjectStorageBackend::Gcs,
            Self::AzureBlob => ObjectStorageBackend::AzureBlob,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudObjectStoreTarget {
    pub provider: CloudObjectProvider,
    pub bucket: String,
    pub prefix: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub region: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
    #[serde(default)]
    pub server_side_encryption: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub kms_key_id: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl CloudObjectStoreTarget {
    #[must_use]
    pub fn s3(bucket: impl Into<String>, prefix: impl Into<String>) -> Self {
        Self::new(CloudObjectProvider::S3Compatible, bucket, prefix)
    }

    #[must_use]
    pub fn gcs(bucket: impl Into<String>, prefix: impl Into<String>) -> Self {
        Self::new(CloudObjectProvider::Gcs, bucket, prefix)
    }

    #[must_use]
    pub fn azure_blob(container: impl Into<String>, prefix: impl Into<String>) -> Self {
        Self::new(CloudObjectProvider::AzureBlob, container, prefix)
    }

    #[must_use]
    pub fn new(
        provider: CloudObjectProvider,
        bucket: impl Into<String>,
        prefix: impl Into<String>,
    ) -> Self {
        Self {
            provider,
            bucket: bucket.into(),
            prefix: prefix.into(),
            region: None,
            endpoint: None,
            server_side_encryption: false,
            kms_key_id: None,
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn with_region(mut self, region: impl Into<String>) -> Self {
        self.region = Some(region.into());
        self
    }
    #[must_use]
    pub fn with_endpoint(mut self, endpoint: impl Into<String>) -> Self {
        self.endpoint = Some(endpoint.into());
        self
    }
    #[must_use]
    pub fn with_kms_key(mut self, key_id: impl Into<String>) -> Self {
        self.server_side_encryption = true;
        self.kms_key_id = Some(key_id.into());
        self
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.bucket.trim().is_empty() {
            return Err(MindError::ObjectStorage {
                reason: "cloud object bucket/container is required".to_owned(),
            });
        }
        if self.prefix.contains("..") || self.prefix.starts_with('/') || self.prefix.contains('\\')
        {
            return Err(MindError::ObjectStorage {
                reason: "cloud object prefix contains unsafe path characters".to_owned(),
            });
        }
        if self.server_side_encryption
            && self
                .kms_key_id
                .as_deref()
                .unwrap_or_default()
                .trim()
                .is_empty()
        {
            return Err(MindError::ObjectStorage {
                reason: "server-side encryption requires a KMS key id".to_owned(),
            });
        }
        Ok(())
    }

    #[must_use]
    pub fn object_key(&self, backup: &MindBackup) -> String {
        let prefix = self.prefix.trim_matches('/');
        let file_name = format!("{}.backup.json", backup.manifest.backup_id);
        if prefix.is_empty() {
            file_name
        } else {
            format!("{prefix}/{file_name}")
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudObjectPutRequest {
    pub request_id: EventId,
    pub provider: CloudObjectProvider,
    pub bucket: String,
    pub key: String,
    pub content_type: String,
    pub body_sha256_hex: String,
    pub body_bytes: usize,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
    pub created_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudObjectGetRequest {
    pub provider: CloudObjectProvider,
    pub bucket: String,
    pub key: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endpoint: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudObjectBackupPlan {
    pub backup_id: EventId,
    pub manifest_hash: String,
    pub target: CloudObjectStoreTarget,
    pub put_request: CloudObjectPutRequest,
    pub get_request: CloudObjectGetRequest,
    pub verification: BackupVerificationReport,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CloudObjectAdapter {
    pub target: CloudObjectStoreTarget,
}

impl CloudObjectAdapter {
    pub fn new(target: CloudObjectStoreTarget) -> MindResult<Self> {
        target.validate()?;
        Ok(Self { target })
    }

    pub fn plan_backup_put(
        &self,
        backup: &MindBackup,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<CloudObjectBackupPlan> {
        let verification = backup.verify(signature_requirement)?;
        let body = serde_json::to_vec(backup)?;
        let body_sha256_hex = sha256_hex(&body);
        let key = self.target.object_key(backup);
        let mut headers = BTreeMap::from([
            ("Content-Type".to_owned(), "application/json".to_owned()),
            (
                "x-mind-backup-id".to_owned(),
                backup.manifest.backup_id.to_string(),
            ),
            (
                "x-mind-backup-hash".to_owned(),
                backup.manifest.backup_hash.clone(),
            ),
            ("x-mind-content-sha256".to_owned(), body_sha256_hex.clone()),
        ]);
        match self.target.provider {
            CloudObjectProvider::S3Compatible => {
                if self.target.server_side_encryption {
                    headers.insert(
                        "x-amz-server-side-encryption".to_owned(),
                        "aws:kms".to_owned(),
                    );
                }
                if let Some(key_id) = &self.target.kms_key_id {
                    headers.insert(
                        "x-amz-server-side-encryption-aws-kms-key-id".to_owned(),
                        key_id.clone(),
                    );
                }
            }
            CloudObjectProvider::Gcs => {
                if let Some(key_id) = &self.target.kms_key_id {
                    headers.insert("x-goog-encryption-kms-key-name".to_owned(), key_id.clone());
                }
            }
            CloudObjectProvider::AzureBlob => {
                headers.insert("x-ms-blob-type".to_owned(), "BlockBlob".to_owned());
                if let Some(key_id) = &self.target.kms_key_id {
                    headers.insert("x-ms-encryption-scope".to_owned(), key_id.clone());
                }
            }
        }
        let put_request = CloudObjectPutRequest {
            request_id: EventId::new(),
            provider: self.target.provider,
            bucket: self.target.bucket.clone(),
            key: key.clone(),
            content_type: "application/json".to_owned(),
            body_sha256_hex,
            body_bytes: body.len(),
            headers,
            metadata: self.target.metadata.clone(),
            endpoint: self.target.endpoint.clone(),
            created_at: OffsetDateTime::now_utc(),
        };
        let get_request = CloudObjectGetRequest {
            provider: self.target.provider,
            bucket: self.target.bucket.clone(),
            key,
            endpoint: self.target.endpoint.clone(),
        };
        Ok(CloudObjectBackupPlan {
            backup_id: backup.manifest.backup_id,
            manifest_hash: hash_serializable(&backup.manifest)?,
            target: self.target.clone(),
            put_request,
            get_request,
            verification,
        })
    }
}

fn sha256_hex(body: &[u8]) -> String {
    let digest = Sha256::digest(body);
    hex::encode(digest)
}
