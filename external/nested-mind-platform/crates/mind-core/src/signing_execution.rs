use crate::{
    ManagedSigningCompletion, ManagedSigningProvider, ManagedSigningRequest, MindError, MindResult,
    ProviderSigningCommand,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VendorSigningExecutionRequest {
    pub execution_id: crate::EventId,
    pub request_id: crate::EventId,
    pub provider: ManagedSigningProvider,
    pub key_id: String,
    pub resource: String,
    pub payload_hash: String,
    pub command: ProviderSigningCommand,
    #[serde(default)]
    pub required_environment: Vec<String>,
    pub timeout_seconds: u64,
    pub created_at: OffsetDateTime,
}

impl VendorSigningExecutionRequest {
    #[must_use]
    pub fn from_request(request: &ManagedSigningRequest) -> Self {
        Self {
            execution_id: crate::EventId::new(),
            request_id: request.request_id,
            provider: request.key.provider,
            key_id: request.key.key_id.clone(),
            resource: request.key.resource.clone(),
            payload_hash: request.payload_hash.clone(),
            command: request.provider_command.clone(),
            required_environment: required_environment_for(request.key.provider),
            timeout_seconds: 30,
            created_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VendorSigningReceipt {
    pub execution_id: crate::EventId,
    pub request_id: crate::EventId,
    pub commit_id: crate::EventId,
    pub provider: ManagedSigningProvider,
    pub key_id: String,
    pub payload_hash: String,
    pub signature_hex: String,
    pub public_key_hex: String,
    pub signer_identity: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub attestation_id: Option<String>,
    pub completed_at: OffsetDateTime,
}

impl VendorSigningReceipt {
    pub fn into_completion(
        self,
        request: &ManagedSigningRequest,
    ) -> MindResult<ManagedSigningCompletion> {
        if self.request_id != request.request_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "vendor signing receipt request id mismatch".to_owned(),
            });
        }
        if self.commit_id != request.commit_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "vendor signing receipt commit id mismatch".to_owned(),
            });
        }
        if self.provider != request.key.provider {
            return Err(MindError::SigningAttestationInvalid {
                reason: "vendor signing receipt provider mismatch".to_owned(),
            });
        }
        if self.key_id != request.key.key_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "vendor signing receipt key id mismatch".to_owned(),
            });
        }
        if self.payload_hash != request.payload_hash {
            return Err(MindError::SigningAttestationInvalid {
                reason: "vendor signing receipt payload hash mismatch".to_owned(),
            });
        }
        if self.public_key_hex != request.key.public_key_hex {
            return Err(MindError::SigningAttestationInvalid {
                reason: "vendor signing receipt public key mismatch".to_owned(),
            });
        }
        Ok(ManagedSigningCompletion {
            request_id: self.request_id,
            commit_id: self.commit_id,
            key_id: self.key_id,
            provider: self.provider,
            payload_hash: self.payload_hash,
            signature_hex: self.signature_hex,
            public_key_hex: self.public_key_hex,
            signer_identity: self.signer_identity,
            attestation_id: self
                .attestation_id
                .or_else(|| Some(self.execution_id.to_string())),
            signed_at: self.completed_at,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VendorSigningAdapterReport {
    pub provider: ManagedSigningProvider,
    pub request_id: crate::EventId,
    pub execution_id: crate::EventId,
    pub ready_for_external_execution: bool,
    #[serde(default)]
    pub required_environment: Vec<String>,
    #[serde(default)]
    pub notes: Vec<String>,
}

impl VendorSigningAdapterReport {
    #[must_use]
    pub fn from_execution_request(request: &VendorSigningExecutionRequest) -> Self {
        Self {
            provider: request.provider,
            request_id: request.request_id,
            execution_id: request.execution_id,
            ready_for_external_execution: true,
            required_environment: request.required_environment.clone(),
            notes: Vec::new(),
        }
    }
}

fn required_environment_for(provider: ManagedSigningProvider) -> Vec<String> {
    match provider {
        ManagedSigningProvider::AwsKms => vec![
            "AWS_REGION".to_owned(),
            "AWS_ACCESS_KEY_ID or workload identity".to_owned(),
        ],
        ManagedSigningProvider::GcpCloudKms => {
            vec!["GOOGLE_APPLICATION_CREDENTIALS or workload identity".to_owned()]
        }
        ManagedSigningProvider::AzureKeyVault => vec![
            "AZURE_TENANT_ID".to_owned(),
            "AZURE_CLIENT_ID or managed identity".to_owned(),
        ],
        ManagedSigningProvider::HashicorpVault => vec![
            "VAULT_ADDR".to_owned(),
            "VAULT_TOKEN or workload identity".to_owned(),
        ],
        ManagedSigningProvider::Pkcs11Hsm => vec![
            "PKCS11_MODULE_PATH".to_owned(),
            "PKCS11_PIN_SOURCE".to_owned(),
        ],
    }
}
