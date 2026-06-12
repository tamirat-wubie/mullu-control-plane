use crate::{
    hash_serializable, Commit, CommitSignature, EventId, MindError, MindId, MindResult,
    SignatureAlgorithm, SignatureAttestation, SignatureBackendKind, SigningBackendKind,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ManagedSigningProvider {
    AwsKms,
    GcpCloudKms,
    AzureKeyVault,
    HashicorpVault,
    Pkcs11Hsm,
}

impl ManagedSigningProvider {
    #[must_use]
    pub fn backend_kind(self) -> SigningBackendKind {
        match self {
            Self::AwsKms => SigningBackendKind::AwsKms,
            Self::GcpCloudKms => SigningBackendKind::GcpCloudKms,
            Self::AzureKeyVault => SigningBackendKind::AzureKeyVault,
            Self::HashicorpVault => SigningBackendKind::HashicorpVault,
            Self::Pkcs11Hsm => SigningBackendKind::Pkcs11Hsm,
        }
    }

    #[must_use]
    pub fn signature_backend_kind(self) -> SignatureBackendKind {
        match self {
            Self::AwsKms | Self::GcpCloudKms | Self::AzureKeyVault => SignatureBackendKind::Kms,
            Self::HashicorpVault => SignatureBackendKind::SecretManager,
            Self::Pkcs11Hsm => SignatureBackendKind::Hsm,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManagedSigningKey {
    pub key_id: String,
    pub provider: ManagedSigningProvider,
    pub resource: String,
    pub algorithm: SignatureAlgorithm,
    pub public_key_hex: String,
}

impl ManagedSigningKey {
    #[must_use]
    pub fn ed25519(
        provider: ManagedSigningProvider,
        key_id: impl Into<String>,
        resource: impl Into<String>,
        public_key_hex: impl Into<String>,
    ) -> Self {
        Self {
            key_id: key_id.into(),
            provider,
            resource: resource.into(),
            algorithm: SignatureAlgorithm::Ed25519,
            public_key_hex: public_key_hex.into(),
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.key_id.trim().is_empty() {
            return Err(MindError::Signing(
                "managed signing key id is required".to_owned(),
            ));
        }
        if self.resource.trim().is_empty() {
            return Err(MindError::Signing(
                "managed signing key resource is required".to_owned(),
            ));
        }
        if self.public_key_hex.trim().is_empty() {
            return Err(MindError::Signing(
                "managed signing public key is required".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManagedSigningRequest {
    pub request_id: EventId,
    pub commit_id: EventId,
    pub mind_id: MindId,
    pub key: ManagedSigningKey,
    pub payload_hash: String,
    pub payload_hex: String,
    pub provider_command: ProviderSigningCommand,
    pub created_at: OffsetDateTime,
}

impl ManagedSigningRequest {
    pub fn from_commit(commit: &Commit, key: ManagedSigningKey) -> MindResult<Self> {
        key.validate()?;
        let payload = commit.signable_payload()?;
        let payload_hash = hash_serializable(&payload)?;
        let payload_hex = hex::encode(payload);
        let provider_command =
            ProviderSigningCommand::for_key(&key, payload_hash.clone(), payload_hex.clone());
        Ok(Self {
            request_id: EventId::new(),
            commit_id: commit.id,
            mind_id: commit.mind_id,
            key,
            payload_hash,
            payload_hex,
            provider_command,
            created_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "provider", rename_all = "snake_case")]
pub enum ProviderSigningCommand {
    AwsKms {
        key_id: String,
        message_type: String,
        signing_algorithm: String,
        payload_hash: String,
        payload_hex: String,
    },
    GcpCloudKms {
        name: String,
        digest_sha256_hex: String,
        payload_hex: String,
    },
    AzureKeyVault {
        key_id: String,
        algorithm: String,
        digest_sha256_hex: String,
        payload_hex: String,
    },
    HashicorpVault {
        transit_key: String,
        hash_algorithm: String,
        digest_sha256_hex: String,
        payload_hex: String,
    },
    Pkcs11Hsm {
        key_label: String,
        mechanism: String,
        payload_hex: String,
    },
}

impl ProviderSigningCommand {
    #[must_use]
    pub fn for_key(key: &ManagedSigningKey, payload_hash: String, payload_hex: String) -> Self {
        match key.provider {
            ManagedSigningProvider::AwsKms => Self::AwsKms {
                key_id: key.resource.clone(),
                message_type: "RAW".to_owned(),
                signing_algorithm: "Ed25519".to_owned(),
                payload_hash,
                payload_hex,
            },
            ManagedSigningProvider::GcpCloudKms => Self::GcpCloudKms {
                name: key.resource.clone(),
                digest_sha256_hex: payload_hash,
                payload_hex,
            },
            ManagedSigningProvider::AzureKeyVault => Self::AzureKeyVault {
                key_id: key.resource.clone(),
                algorithm: "EdDSA".to_owned(),
                digest_sha256_hex: payload_hash,
                payload_hex,
            },
            ManagedSigningProvider::HashicorpVault => Self::HashicorpVault {
                transit_key: key.resource.clone(),
                hash_algorithm: "sha2-256".to_owned(),
                digest_sha256_hex: payload_hash,
                payload_hex,
            },
            ManagedSigningProvider::Pkcs11Hsm => Self::Pkcs11Hsm {
                key_label: key.resource.clone(),
                mechanism: "CKM_EDDSA".to_owned(),
                payload_hex,
            },
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManagedSigningCompletion {
    pub request_id: EventId,
    pub commit_id: EventId,
    pub key_id: String,
    pub provider: ManagedSigningProvider,
    pub payload_hash: String,
    pub signature_hex: String,
    pub public_key_hex: String,
    pub signer_identity: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub attestation_id: Option<String>,
    pub signed_at: OffsetDateTime,
}

impl ManagedSigningCompletion {
    pub fn validate_for(&self, request: &ManagedSigningRequest) -> MindResult<()> {
        if self.request_id != request.request_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "managed signing request id mismatch".to_owned(),
            });
        }
        if self.commit_id != request.commit_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "managed signing commit id mismatch".to_owned(),
            });
        }
        if self.key_id != request.key.key_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "managed signing key id mismatch".to_owned(),
            });
        }
        if self.provider != request.key.provider {
            return Err(MindError::SigningAttestationInvalid {
                reason: "managed signing provider mismatch".to_owned(),
            });
        }
        if self.payload_hash != request.payload_hash {
            return Err(MindError::SigningAttestationInvalid {
                reason: "managed signing payload hash mismatch".to_owned(),
            });
        }
        if self.public_key_hex != request.key.public_key_hex {
            return Err(MindError::SigningAttestationInvalid {
                reason: "managed signing public key mismatch".to_owned(),
            });
        }
        Ok(())
    }

    #[must_use]
    pub fn into_commit_signature(self, key: &ManagedSigningKey) -> CommitSignature {
        CommitSignature {
            algorithm: key.algorithm,
            key_id: key.key_id.clone(),
            public_key_hex: key.public_key_hex.clone(),
            signature_hex: self.signature_hex,
            attestation: Some(
                SignatureAttestation::new(
                    key.provider.signature_backend_kind(),
                    key.resource.clone(),
                    self.signer_identity,
                )
                .with_attestation_id(
                    self.attestation_id
                        .unwrap_or_else(|| self.request_id.to_string()),
                ),
            ),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManagedSigningAdapter {
    pub key: ManagedSigningKey,
}

impl ManagedSigningAdapter {
    pub fn new(key: ManagedSigningKey) -> MindResult<Self> {
        key.validate()?;
        Ok(Self { key })
    }

    pub fn prepare(&self, commit: &Commit) -> MindResult<ManagedSigningRequest> {
        ManagedSigningRequest::from_commit(commit, self.key.clone())
    }

    pub fn complete(
        &self,
        commit: &mut Commit,
        request: &ManagedSigningRequest,
        completion: ManagedSigningCompletion,
    ) -> MindResult<()> {
        if commit.signature.is_some() {
            return Err(MindError::CommitAlreadySigned {
                commit_id: commit.id,
            });
        }
        if commit.id != request.commit_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "commit does not match managed signing request".to_owned(),
            });
        }
        completion.validate_for(request)?;
        let signature = completion.into_commit_signature(&self.key);
        commit.signature = Some(signature);
        commit.verify_signature()?;
        Ok(())
    }
}
