use crate::{
    hash_serializable, Commit, CommitSignature, Ed25519CommitSigner, EventId, MindError, MindId,
    MindResult, SignatureAlgorithm,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum SigningBackendKind {
    LocalEd25519,
    ExternalSigner,
    SecretManager,
    Hsm,
    Kms,
    ExternalRequest,
    AwsKms,
    GcpCloudKms,
    AzureKeyVault,
    HashicorpVault,
    Pkcs11Hsm,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningBackendStatus {
    pub backend: SigningBackendKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key_id: Option<String>,
    pub online: bool,
    pub can_sign_inline: bool,
    pub requires_external_completion: bool,
}

impl SigningBackendStatus {
    #[must_use]
    pub fn disabled() -> Self {
        Self {
            backend: SigningBackendKind::ExternalRequest,
            key_id: None,
            online: false,
            can_sign_inline: false,
            requires_external_completion: false,
        }
    }

    #[must_use]
    pub fn local_ed25519(key_id: impl Into<String>) -> Self {
        Self {
            backend: SigningBackendKind::LocalEd25519,
            key_id: Some(key_id.into()),
            online: true,
            can_sign_inline: true,
            requires_external_completion: false,
        }
    }

    #[must_use]
    pub fn external(backend: SigningBackendKind, key_id: impl Into<String>) -> Self {
        Self {
            backend,
            key_id: Some(key_id.into()),
            online: true,
            can_sign_inline: false,
            requires_external_completion: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningKeyReference {
    pub key_id: String,
    pub backend: SigningBackendKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resource: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub public_key_hex: Option<String>,
}

impl SigningKeyReference {
    #[must_use]
    pub fn local_ed25519(key_id: impl Into<String>, public_key_hex: impl Into<String>) -> Self {
        Self {
            key_id: key_id.into(),
            backend: SigningBackendKind::LocalEd25519,
            resource: None,
            public_key_hex: Some(public_key_hex.into()),
        }
    }

    #[must_use]
    pub fn external(
        key_id: impl Into<String>,
        backend: SigningBackendKind,
        resource: impl Into<String>,
    ) -> Self {
        Self {
            key_id: key_id.into(),
            backend,
            resource: Some(resource.into()),
            public_key_hex: None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningProviderPolicy {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_key: Option<SigningKeyReference>,
    pub require_commit_signatures: bool,
    pub require_attestation: bool,
}

impl SigningProviderPolicy {
    #[must_use]
    pub fn unsigned_development() -> Self {
        Self {
            active_key: None,
            require_commit_signatures: false,
            require_attestation: false,
        }
    }

    #[must_use]
    pub fn local_ed25519(
        key_id: impl Into<String>,
        public_key_hex: impl Into<String>,
        require_commit_signatures: bool,
    ) -> Self {
        Self {
            active_key: Some(SigningKeyReference::local_ed25519(key_id, public_key_hex)),
            require_commit_signatures,
            require_attestation: false,
        }
    }

    #[must_use]
    pub fn external_required(key: SigningKeyReference) -> Self {
        Self {
            active_key: Some(key),
            require_commit_signatures: true,
            require_attestation: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CommitSigningRequest {
    pub request_id: EventId,
    pub commit_id: EventId,
    pub mind_id: MindId,
    pub key_id: String,
    pub backend: SigningBackendKind,
    pub payload_hash: String,
    pub payload_hex: String,
    pub created_at: OffsetDateTime,
}

impl CommitSigningRequest {
    pub fn from_commit(commit: &Commit, key: &SigningKeyReference) -> MindResult<Self> {
        let payload = commit.signable_payload()?;
        let payload_hash = hash_serializable(&payload)?;
        Ok(Self {
            request_id: EventId::new(),
            commit_id: commit.id,
            mind_id: commit.mind_id,
            key_id: key.key_id.clone(),
            backend: key.backend,
            payload_hash,
            payload_hex: hex::encode(payload),
            created_at: OffsetDateTime::now_utc(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningAttestation {
    pub request_id: EventId,
    pub commit_id: EventId,
    pub key_id: String,
    pub backend: SigningBackendKind,
    pub payload_hash: String,
    pub signer_identity: String,
    pub signed_at: OffsetDateTime,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signature: Option<CommitSignature>,
}

impl SigningAttestation {
    #[must_use]
    pub fn from_signature(
        request: &CommitSigningRequest,
        signer_identity: impl Into<String>,
        signature: CommitSignature,
    ) -> Self {
        Self {
            request_id: request.request_id,
            commit_id: request.commit_id,
            key_id: request.key_id.clone(),
            backend: request.backend,
            payload_hash: request.payload_hash.clone(),
            signer_identity: signer_identity.into(),
            signed_at: OffsetDateTime::now_utc(),
            signature: Some(signature),
        }
    }

    pub fn validate_for(&self, request: &CommitSigningRequest) -> MindResult<()> {
        if self.request_id != request.request_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "request id mismatch".to_owned(),
            });
        }
        if self.commit_id != request.commit_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "commit id mismatch".to_owned(),
            });
        }
        if self.key_id != request.key_id {
            return Err(MindError::SigningAttestationInvalid {
                reason: "key id mismatch".to_owned(),
            });
        }
        if self.backend != request.backend {
            return Err(MindError::SigningAttestationInvalid {
                reason: "signing backend mismatch".to_owned(),
            });
        }
        if self.payload_hash != request.payload_hash {
            return Err(MindError::SigningAttestationInvalid {
                reason: "payload hash mismatch".to_owned(),
            });
        }
        let Some(signature) = &self.signature else {
            return Err(MindError::SigningAttestationInvalid {
                reason: "attestation does not contain a signature".to_owned(),
            });
        };
        if signature.algorithm != SignatureAlgorithm::Ed25519 {
            return Err(MindError::SigningAttestationInvalid {
                reason: "unsupported signature algorithm".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExternalSigningRequest {
    pub request_id: EventId,
    pub commit_id: EventId,
    pub mind_id: MindId,
    pub backend: SigningBackendKind,
    pub key_id: String,
    pub payload_hash: String,
    pub signable_payload_hex: String,
    pub created_at: OffsetDateTime,
}

impl ExternalSigningRequest {
    pub fn from_commit(
        commit: &Commit,
        backend: SigningBackendKind,
        key_id: impl Into<String>,
    ) -> MindResult<Self> {
        let payload = commit.signable_payload()?;
        Ok(Self {
            request_id: EventId::new(),
            commit_id: commit.id,
            mind_id: commit.mind_id,
            backend,
            key_id: key_id.into(),
            payload_hash: hash_serializable(&payload)?,
            signable_payload_hex: hex::encode(payload),
            created_at: OffsetDateTime::now_utc(),
        })
    }
}

pub trait CommitSigningService {
    fn sign_commit(&self, commit: &mut Commit) -> MindResult<SigningBackendStatus>;
}

#[derive(Clone, Debug)]
pub struct LocalEd25519SigningService {
    signer: Ed25519CommitSigner,
}

impl LocalEd25519SigningService {
    #[must_use]
    pub fn new(signer: Ed25519CommitSigner) -> Self {
        Self { signer }
    }

    #[must_use]
    pub fn key_id(&self) -> &str {
        self.signer.key_id()
    }

    #[must_use]
    pub fn signer(&self) -> &Ed25519CommitSigner {
        &self.signer
    }
}

impl CommitSigningService for LocalEd25519SigningService {
    fn sign_commit(&self, commit: &mut Commit) -> MindResult<SigningBackendStatus> {
        commit.sign_with(&self.signer)?;
        Ok(SigningBackendStatus::local_ed25519(
            self.signer.key_id().to_owned(),
        ))
    }
}

#[derive(Clone, Debug)]
pub struct ExternalRequestSigningService {
    backend: SigningBackendKind,
    key_id: String,
}

impl ExternalRequestSigningService {
    #[must_use]
    pub fn new(backend: SigningBackendKind, key_id: impl Into<String>) -> Self {
        Self {
            backend,
            key_id: key_id.into(),
        }
    }

    pub fn request_for_commit(&self, commit: &Commit) -> MindResult<ExternalSigningRequest> {
        ExternalSigningRequest::from_commit(commit, self.backend, self.key_id.clone())
    }

    #[must_use]
    pub fn status(&self) -> SigningBackendStatus {
        SigningBackendStatus::external(self.backend, self.key_id.clone())
    }
}

impl CommitSigningService for ExternalRequestSigningService {
    fn sign_commit(&self, commit: &mut Commit) -> MindResult<SigningBackendStatus> {
        let request = self.request_for_commit(commit)?;
        Err(MindError::Signing(format!(
            "external signing request {} must be completed by backend {:?}",
            request.request_id, self.backend
        )))
    }
}
