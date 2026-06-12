use crate::{
    hash_serializable, EventId, MindError, MindResult, ProviderAdapterKind, ProviderCommandKind,
    ProviderExecutionRequest, ProviderExecutionStatus,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum DirectProviderSdk {
    AwsKms,
    AwsS3,
    GcpCloudKms,
    Gcs,
    AzureKeyVault,
    AzureBlob,
    HashicorpVault,
    Pkcs11Hsm,
    HttpGateway,
    LocalMirror,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSdkInvocation {
    pub invocation_id: EventId,
    pub sdk: DirectProviderSdk,
    pub command_kind: ProviderCommandKind,
    pub target: String,
    pub request_hash: String,
    pub idempotency_key: String,
    pub command_json: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub created_at: OffsetDateTime,
}

impl ProviderSdkInvocation {
    pub fn from_execution_request(request: &ProviderExecutionRequest) -> MindResult<Self> {
        let sdk = map_adapter_to_sdk(request.adapter, request.command_kind)?;
        let command_json = serde_json::to_string(request)?;
        let idempotency_key = hash_serializable(&(
            sdk,
            request.command_kind,
            &request.target,
            &request.payload_hash,
        ))?;
        Ok(Self {
            invocation_id: EventId::new(),
            sdk,
            command_kind: request.command_kind,
            target: request.target.clone(),
            request_hash: request.payload_hash.clone(),
            idempotency_key,
            command_json,
            metadata: request.metadata.clone(),
            created_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        if self.target.trim().is_empty() {
            return Err(MindError::Store(
                "provider SDK invocation target is required".to_owned(),
            ));
        }
        if self.request_hash.trim().is_empty() {
            return Err(MindError::Store(
                "provider SDK invocation request hash is required".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSdkReceipt {
    pub receipt_id: EventId,
    pub invocation_id: EventId,
    pub sdk: DirectProviderSdk,
    pub command_kind: ProviderCommandKind,
    pub target: String,
    pub status: ProviderExecutionStatus,
    pub expected_request_hash: String,
    pub observed_request_hash: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_request_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub completed_at: OffsetDateTime,
}

impl ProviderSdkReceipt {
    #[must_use]
    pub fn dry_run_success(invocation: &ProviderSdkInvocation) -> Self {
        Self {
            receipt_id: EventId::new(),
            invocation_id: invocation.invocation_id,
            sdk: invocation.sdk,
            command_kind: invocation.command_kind,
            target: invocation.target.clone(),
            status: ProviderExecutionStatus::Succeeded,
            expected_request_hash: invocation.request_hash.clone(),
            observed_request_hash: invocation.request_hash.clone(),
            provider_request_id: Some(format!("dry-run-{}", invocation.invocation_id)),
            error: None,
            metadata: invocation.metadata.clone(),
            completed_at: OffsetDateTime::now_utc(),
        }
    }

    pub fn verify_for(&self, invocation: &ProviderSdkInvocation) -> MindResult<()> {
        invocation.verify()?;
        if self.invocation_id != invocation.invocation_id
            || self.sdk != invocation.sdk
            || self.command_kind != invocation.command_kind
            || self.target != invocation.target
        {
            return Err(MindError::Store(
                "provider SDK receipt target mismatch".to_owned(),
            ));
        }
        if self.expected_request_hash != invocation.request_hash {
            return Err(MindError::Store(
                "provider SDK receipt expected hash mismatch".to_owned(),
            ));
        }
        if self.status == ProviderExecutionStatus::Succeeded
            && self.observed_request_hash != invocation.request_hash
        {
            return Err(MindError::Store(
                "provider SDK receipt observed hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProviderSdkAdapterReport {
    pub report_id: EventId,
    pub invocation: ProviderSdkInvocation,
    pub receipt: ProviderSdkReceipt,
    pub executed_at: OffsetDateTime,
}

impl ProviderSdkAdapterReport {
    pub fn dry_run(request: &ProviderExecutionRequest) -> MindResult<Self> {
        let invocation = ProviderSdkInvocation::from_execution_request(request)?;
        let receipt = ProviderSdkReceipt::dry_run_success(&invocation);
        receipt.verify_for(&invocation)?;
        Ok(Self {
            report_id: EventId::new(),
            invocation,
            receipt,
            executed_at: OffsetDateTime::now_utc(),
        })
    }
}

fn map_adapter_to_sdk(
    adapter: ProviderAdapterKind,
    command: ProviderCommandKind,
) -> MindResult<DirectProviderSdk> {
    match (adapter, command) {
        (ProviderAdapterKind::AwsSdk, ProviderCommandKind::KmsSign) => {
            Ok(DirectProviderSdk::AwsKms)
        }
        (
            ProviderAdapterKind::AwsSdk,
            ProviderCommandKind::ObjectPut | ProviderCommandKind::ObjectGet,
        ) => Ok(DirectProviderSdk::AwsS3),
        (ProviderAdapterKind::GcpSdk, ProviderCommandKind::KmsSign) => {
            Ok(DirectProviderSdk::GcpCloudKms)
        }
        (
            ProviderAdapterKind::GcpSdk,
            ProviderCommandKind::ObjectPut | ProviderCommandKind::ObjectGet,
        ) => Ok(DirectProviderSdk::Gcs),
        (ProviderAdapterKind::AzureSdk, ProviderCommandKind::KmsSign) => {
            Ok(DirectProviderSdk::AzureKeyVault)
        }
        (
            ProviderAdapterKind::AzureSdk,
            ProviderCommandKind::ObjectPut | ProviderCommandKind::ObjectGet,
        ) => Ok(DirectProviderSdk::AzureBlob),
        (ProviderAdapterKind::VaultSdk, ProviderCommandKind::KmsSign) => {
            Ok(DirectProviderSdk::HashicorpVault)
        }
        (ProviderAdapterKind::Pkcs11, ProviderCommandKind::KmsSign) => {
            Ok(DirectProviderSdk::Pkcs11Hsm)
        }
        (ProviderAdapterKind::HttpGateway, _) | (ProviderAdapterKind::SignedUrl, _) => {
            Ok(DirectProviderSdk::HttpGateway)
        }
        (ProviderAdapterKind::LocalMirror, _) => Ok(DirectProviderSdk::LocalMirror),
        _ => Err(MindError::Store(
            "provider SDK adapter does not support requested command".to_owned(),
        )),
    }
}
