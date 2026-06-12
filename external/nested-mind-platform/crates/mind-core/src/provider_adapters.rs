use crate::{
    hash_serializable, CloudObjectProvider, EventId, ManagedSigningProvider, ManagedSigningRequest,
    MindError, MindResult, ReplicationEnvelope, VendorSigningExecutionRequest,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ProviderAdapterKind {
    AwsSdk,
    GcpSdk,
    AzureSdk,
    VaultSdk,
    Pkcs11,
    HttpGateway,
    SignedUrl,
    LocalMirror,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ProviderCommandKind {
    KmsSign,
    ObjectPut,
    ObjectGet,
    OidcRefresh,
    ReplicationPush,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ProviderExecutionStatus {
    Planned,
    Succeeded,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderExecutionRequest {
    pub execution_id: EventId,
    pub adapter: ProviderAdapterKind,
    pub command_kind: ProviderCommandKind,
    pub target: String,
    pub payload_hash: String,
    pub payload_bytes: usize,
    pub idempotency_key: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub created_at: OffsetDateTime,
}

impl ProviderExecutionRequest {
    pub fn new<T: Serialize>(
        adapter: ProviderAdapterKind,
        command_kind: ProviderCommandKind,
        target: impl Into<String>,
        payload: &T,
    ) -> MindResult<Self> {
        let target = target.into();
        if target.trim().is_empty() {
            return Err(MindError::Store(
                "provider execution target is required".to_owned(),
            ));
        }
        let payload_hash = hash_serializable(payload)?;
        let payload_bytes = serde_json::to_vec(payload)?.len();
        let idempotency_key = hash_serializable(&(adapter, command_kind, &target, &payload_hash))?;
        Ok(Self {
            execution_id: EventId::new(),
            adapter,
            command_kind,
            target,
            payload_hash,
            payload_bytes,
            idempotency_key,
            metadata: BTreeMap::new(),
            created_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn from_managed_signing(
        request: &ManagedSigningRequest,
        adapter: ProviderAdapterKind,
    ) -> MindResult<Self> {
        let target = format!("{:?}:{}", request.key.provider, request.key.resource);
        let mut execution = Self::new(
            adapter,
            ProviderCommandKind::KmsSign,
            target,
            &request.provider_command,
        )?;
        execution
            .metadata
            .insert("request_id".to_owned(), request.request_id.to_string());
        execution
            .metadata
            .insert("commit_id".to_owned(), request.commit_id.to_string());
        execution
            .metadata
            .insert("key_id".to_owned(), request.key.key_id.clone());
        execution.payload_hash = request.payload_hash.clone();
        Ok(execution)
    }

    pub fn from_vendor_signing(
        request: &VendorSigningExecutionRequest,
        adapter: ProviderAdapterKind,
    ) -> MindResult<Self> {
        let target = format!("{:?}:{}", request.provider, request.resource);
        let mut execution = Self::new(
            adapter,
            ProviderCommandKind::KmsSign,
            target,
            &request.command,
        )?;
        execution
            .metadata
            .insert("request_id".to_owned(), request.request_id.to_string());
        execution
            .metadata
            .insert("execution_id".to_owned(), request.execution_id.to_string());
        execution
            .metadata
            .insert("key_id".to_owned(), request.key_id.clone());
        execution.payload_hash = request.payload_hash.clone();
        Ok(execution)
    }

    pub fn from_replication_envelope(
        envelope: &ReplicationEnvelope,
        target_node_id: impl Into<String>,
    ) -> MindResult<Self> {
        let target_node_id = target_node_id.into();
        let mut execution = Self::new(
            ProviderAdapterKind::HttpGateway,
            ProviderCommandKind::ReplicationPush,
            target_node_id,
            envelope,
        )?;
        execution
            .metadata
            .insert("envelope_id".to_owned(), envelope.envelope_id.to_string());
        execution
            .metadata
            .insert("batch_id".to_owned(), envelope.batch.batch_id.to_string());
        execution.payload_hash = envelope.body_hash.clone();
        Ok(execution)
    }

    pub fn for_object_put<T: Serialize>(
        provider: CloudObjectProvider,
        bucket: impl Into<String>,
        key: impl Into<String>,
        payload: &T,
    ) -> MindResult<Self> {
        let bucket = bucket.into();
        let key = key.into();
        let adapter = match provider {
            CloudObjectProvider::S3Compatible => ProviderAdapterKind::AwsSdk,
            CloudObjectProvider::Gcs => ProviderAdapterKind::GcpSdk,
            CloudObjectProvider::AzureBlob => ProviderAdapterKind::AzureSdk,
        };
        let mut execution = Self::new(
            adapter,
            ProviderCommandKind::ObjectPut,
            format!("{bucket}/{key}"),
            payload,
        )?;
        execution.metadata.insert("bucket".to_owned(), bucket);
        execution.metadata.insert("key".to_owned(), key);
        execution
            .metadata
            .insert("provider".to_owned(), format!("{:?}", provider));
        Ok(execution)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderExecutionReceipt {
    pub receipt_id: EventId,
    pub execution_id: EventId,
    pub adapter: ProviderAdapterKind,
    pub command_kind: ProviderCommandKind,
    pub target: String,
    pub status: ProviderExecutionStatus,
    pub expected_payload_hash: String,
    pub observed_payload_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub external_receipt_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub completed_at: OffsetDateTime,
}

impl ProviderExecutionReceipt {
    #[must_use]
    pub fn succeeded(
        request: &ProviderExecutionRequest,
        observed_payload_hash: impl Into<String>,
    ) -> Self {
        let observed_payload_hash = observed_payload_hash.into();
        Self {
            receipt_id: EventId::new(),
            execution_id: request.execution_id,
            adapter: request.adapter,
            command_kind: request.command_kind,
            target: request.target.clone(),
            status: if observed_payload_hash == request.payload_hash {
                ProviderExecutionStatus::Succeeded
            } else {
                ProviderExecutionStatus::Failed
            },
            expected_payload_hash: request.payload_hash.clone(),
            observed_payload_hash,
            external_receipt_id: None,
            error: None,
            metadata: request.metadata.clone(),
            completed_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn failed(request: &ProviderExecutionRequest, error: impl Into<String>) -> Self {
        Self {
            receipt_id: EventId::new(),
            execution_id: request.execution_id,
            adapter: request.adapter,
            command_kind: request.command_kind,
            target: request.target.clone(),
            status: ProviderExecutionStatus::Failed,
            expected_payload_hash: request.payload_hash.clone(),
            observed_payload_hash: String::new(),
            external_receipt_id: None,
            error: Some(error.into()),
            metadata: request.metadata.clone(),
            completed_at: OffsetDateTime::now_utc(),
        }
    }

    pub fn verify_for(&self, request: &ProviderExecutionRequest) -> MindResult<()> {
        if self.execution_id != request.execution_id {
            return Err(MindError::Store(
                "provider execution receipt id mismatch".to_owned(),
            ));
        }
        if self.adapter != request.adapter
            || self.command_kind != request.command_kind
            || self.target != request.target
        {
            return Err(MindError::Store(
                "provider execution receipt target mismatch".to_owned(),
            ));
        }
        if self.expected_payload_hash != request.payload_hash {
            return Err(MindError::Store(
                "provider execution expected hash mismatch".to_owned(),
            ));
        }
        if self.status == ProviderExecutionStatus::Succeeded
            && self.observed_payload_hash != request.payload_hash
        {
            return Err(MindError::Store(
                "provider execution observed hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[must_use]
pub fn signing_provider_adapter(provider: ManagedSigningProvider) -> ProviderAdapterKind {
    match provider {
        ManagedSigningProvider::AwsKms => ProviderAdapterKind::AwsSdk,
        ManagedSigningProvider::GcpCloudKms => ProviderAdapterKind::GcpSdk,
        ManagedSigningProvider::AzureKeyVault => ProviderAdapterKind::AzureSdk,
        ManagedSigningProvider::HashicorpVault => ProviderAdapterKind::VaultSdk,
        ManagedSigningProvider::Pkcs11Hsm => ProviderAdapterKind::Pkcs11,
    }
}
