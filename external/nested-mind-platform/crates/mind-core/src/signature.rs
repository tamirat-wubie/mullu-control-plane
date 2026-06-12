use crate::{
    Commit, EventId, Judgment, LawbookTransition, MindError, MindId, MindResult, StatePatch,
    TopologyEffect,
};
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

const ED25519_SECRET_LENGTH: usize = 32;
const ED25519_PUBLIC_LENGTH: usize = 32;
const ED25519_SIGNATURE_LENGTH: usize = 64;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SignatureAlgorithm {
    Ed25519,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SignatureBackendKind {
    Software,
    SecretManager,
    Hsm,
    Kms,
    ExternalService,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SignatureAttestation {
    pub backend: SignatureBackendKind,
    pub key_uri: String,
    pub signer_identity: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub attestation_id: Option<String>,
}

impl SignatureAttestation {
    #[must_use]
    pub fn new(
        backend: SignatureBackendKind,
        key_uri: impl Into<String>,
        signer_identity: impl Into<String>,
    ) -> Self {
        Self {
            backend,
            key_uri: key_uri.into(),
            signer_identity: signer_identity.into(),
            attestation_id: None,
        }
    }

    #[must_use]
    pub fn with_attestation_id(mut self, attestation_id: impl Into<String>) -> Self {
        self.attestation_id = Some(attestation_id.into());
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CommitSignature {
    pub algorithm: SignatureAlgorithm,
    pub key_id: String,
    pub public_key_hex: String,
    pub signature_hex: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub attestation: Option<SignatureAttestation>,
}

pub trait CommitSigner: Send + Sync {
    fn key_id(&self) -> &str;
    fn public_key_hex(&self) -> String;
    fn sign_commit(&self, commit: &Commit) -> MindResult<CommitSignature>;
}

#[derive(Clone, Debug)]
pub struct Ed25519CommitSigner {
    key_id: String,
    signing_key: SigningKey,
    attestation: Option<SignatureAttestation>,
}

impl Ed25519CommitSigner {
    #[must_use]
    pub fn from_seed(key_id: impl Into<String>, seed: [u8; ED25519_SECRET_LENGTH]) -> Self {
        Self {
            key_id: key_id.into(),
            signing_key: SigningKey::from_bytes(&seed),
            attestation: None,
        }
    }
    pub fn from_seed_hex(key_id: impl Into<String>, seed_hex: &str) -> MindResult<Self> {
        Ok(Self::from_seed(
            key_id,
            decode_hex_array::<ED25519_SECRET_LENGTH>(seed_hex)?,
        ))
    }
    #[must_use]
    pub fn key_id(&self) -> &str {
        &self.key_id
    }
    #[must_use]
    pub fn public_key_hex(&self) -> String {
        hex::encode(self.signing_key.verifying_key().to_bytes())
    }
    #[must_use]
    pub fn with_attestation(mut self, attestation: SignatureAttestation) -> Self {
        self.attestation = Some(attestation);
        self
    }
    #[must_use]
    pub fn attestation(&self) -> Option<&SignatureAttestation> {
        self.attestation.as_ref()
    }
    pub fn sign_commit(&self, commit: &Commit) -> MindResult<CommitSignature> {
        let signature: Signature = self.signing_key.sign(&commit.signable_payload()?);
        Ok(CommitSignature {
            algorithm: SignatureAlgorithm::Ed25519,
            key_id: self.key_id.clone(),
            public_key_hex: self.public_key_hex(),
            signature_hex: hex::encode(signature.to_bytes()),
            attestation: self.attestation.clone(),
        })
    }
}

impl CommitSigner for Ed25519CommitSigner {
    fn key_id(&self) -> &str {
        self.key_id()
    }
    fn public_key_hex(&self) -> String {
        self.public_key_hex()
    }
    fn sign_commit(&self, commit: &Commit) -> MindResult<CommitSignature> {
        Ed25519CommitSigner::sign_commit(self, commit)
    }
}

impl Commit {
    pub fn signable_payload(&self) -> MindResult<Vec<u8>> {
        let payload = CommitSignablePayload {
            id: self.id,
            proposal_id: self.proposal_id,
            mind_id: self.mind_id,
            parent_commit: self.parent_commit,
            actor: &self.actor,
            reason: &self.reason,
            at: self.at,
            patch: &self.patch,
            topology: &self.topology,
            lawbook_transition: self.lawbook_transition.as_ref(),
            before_hash: &self.before_hash,
            after_hash: &self.after_hash,
            judgment: &self.judgment,
        };
        Ok(serde_json::to_vec(&payload)?)
    }
    pub fn sign_with<S: CommitSigner>(&mut self, signer: &S) -> MindResult<()> {
        if self.signature.is_some() {
            return Err(MindError::CommitAlreadySigned { commit_id: self.id });
        }
        self.signature = Some(signer.sign_commit(self)?);
        Ok(())
    }
    pub fn verify_signature(&self) -> MindResult<()> {
        let Some(signature) = &self.signature else {
            return Err(MindError::CommitUnsigned { commit_id: self.id });
        };
        signature.verify_commit(self)
    }
    pub fn require_valid_signature(&self) -> MindResult<()> {
        self.verify_signature()
    }
}

impl CommitSignature {
    pub fn verify_commit(&self, commit: &Commit) -> MindResult<()> {
        match self.algorithm {
            SignatureAlgorithm::Ed25519 => self.verify_ed25519(commit),
        }
    }
    fn verify_ed25519(&self, commit: &Commit) -> MindResult<()> {
        let public_key_bytes = decode_hex_array::<ED25519_PUBLIC_LENGTH>(&self.public_key_hex)?;
        let signature_bytes = decode_hex_array::<ED25519_SIGNATURE_LENGTH>(&self.signature_hex)?;
        let verifying_key = VerifyingKey::from_bytes(&public_key_bytes).map_err(|e| {
            MindError::CommitSignatureInvalid {
                commit_id: commit.id,
                reason: e.to_string(),
            }
        })?;
        let signature = Signature::from_bytes(&signature_bytes);
        verifying_key
            .verify_strict(&commit.signable_payload()?, &signature)
            .map_err(|e| MindError::CommitSignatureInvalid {
                commit_id: commit.id,
                reason: e.to_string(),
            })
    }
}

#[derive(Serialize)]
struct CommitSignablePayload<'a> {
    id: EventId,
    proposal_id: EventId,
    mind_id: MindId,
    parent_commit: Option<EventId>,
    actor: &'a str,
    reason: &'a str,
    at: OffsetDateTime,
    patch: &'a StatePatch,
    topology: &'a [TopologyEffect],
    lawbook_transition: Option<&'a LawbookTransition>,
    before_hash: &'a str,
    after_hash: &'a str,
    judgment: &'a Judgment,
}

fn decode_hex_array<const N: usize>(input: &str) -> MindResult<[u8; N]> {
    let bytes = hex::decode(input)?;
    if bytes.len() != N {
        return Err(MindError::InvalidKeyLength {
            expected: N,
            actual: bytes.len(),
        });
    }
    let mut array = [0_u8; N];
    array.copy_from_slice(&bytes);
    Ok(array)
}
