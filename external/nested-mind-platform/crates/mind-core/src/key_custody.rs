use crate::{Commit, MindError, MindResult, SignatureAlgorithm};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum KeyCustodyBackend {
    LocalRuntime,
    EnvironmentSecret,
    SecretManager,
    HsmKms,
    ExternalSigner,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SigningKeyState {
    Active,
    Rotating,
    Retired,
    Revoked,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningKeyDescriptor {
    pub key_id: String,
    pub algorithm: SignatureAlgorithm,
    pub backend: KeyCustodyBackend,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub public_key_hex: Option<String>,
    pub state: SigningKeyState,
    #[serde(default)]
    pub attestation: BTreeMap<String, String>,
}

impl SigningKeyDescriptor {
    #[must_use]
    pub fn new(key_id: impl Into<String>, backend: KeyCustodyBackend) -> Self {
        Self { key_id: key_id.into(), algorithm: SignatureAlgorithm::Ed25519, backend, public_key_hex: None, state: SigningKeyState::Active, attestation: BTreeMap::new() }
    }
    #[must_use]
    pub fn with_public_key_hex(mut self, public_key_hex: impl Into<String>) -> Self { self.public_key_hex = Some(public_key_hex.into()); self }
    #[must_use]
    pub fn with_state(mut self, state: SigningKeyState) -> Self { self.state = state; self }
    #[must_use]
    pub fn with_attestation(mut self, key: impl Into<String>, value: impl Into<String>) -> Self { self.attestation.insert(key.into(), value.into()); self }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningPolicy {
    pub require_external_custody: bool,
    #[serde(default)]
    pub allowed_backends: BTreeSet<KeyCustodyBackend>,
    #[serde(default)]
    pub trusted_key_ids: BTreeSet<String>,
    pub reject_retired_keys: bool,
}

impl Default for SigningPolicy {
    fn default() -> Self { Self::production_default() }
}

impl SigningPolicy {
    #[must_use]
    pub fn production_default() -> Self {
        Self { require_external_custody: false, allowed_backends: BTreeSet::from([KeyCustodyBackend::LocalRuntime, KeyCustodyBackend::EnvironmentSecret, KeyCustodyBackend::SecretManager, KeyCustodyBackend::HsmKms, KeyCustodyBackend::ExternalSigner]), trusted_key_ids: BTreeSet::new(), reject_retired_keys: true }
    }
    #[must_use]
    pub fn external_custody_required(mut self) -> Self {
        self.require_external_custody = true;
        self.allowed_backends.remove(&KeyCustodyBackend::LocalRuntime);
        self.allowed_backends.remove(&KeyCustodyBackend::EnvironmentSecret);
        self
    }
    #[must_use]
    pub fn trust_key_id(mut self, key_id: impl Into<String>) -> Self { self.trusted_key_ids.insert(key_id.into()); self }
    pub fn validate_descriptor(&self, descriptor: &SigningKeyDescriptor) -> MindResult<()> {
        if !self.allowed_backends.contains(&descriptor.backend) { return Err(MindError::SigningPolicyRejected { reason: format!("backend {:?} is not allowed", descriptor.backend) }); }
        if self.require_external_custody && matches!(descriptor.backend, KeyCustodyBackend::LocalRuntime | KeyCustodyBackend::EnvironmentSecret) { return Err(MindError::SigningPolicyRejected { reason: "external custody is required".to_owned() }); }
        if !self.trusted_key_ids.is_empty() && !self.trusted_key_ids.contains(&descriptor.key_id) { return Err(MindError::SigningPolicyRejected { reason: format!("key id `{}` is not trusted", descriptor.key_id) }); }
        match descriptor.state {
            SigningKeyState::Active | SigningKeyState::Rotating => Ok(()),
            SigningKeyState::Retired if !self.reject_retired_keys => Ok(()),
            SigningKeyState::Retired => Err(MindError::SigningPolicyRejected { reason: format!("key `{}` is retired", descriptor.key_id) }),
            SigningKeyState::Revoked => Err(MindError::SigningPolicyRejected { reason: format!("key `{}` is revoked", descriptor.key_id) }),
        }
    }
    pub fn validate_commit(&self, commit: &Commit, descriptor: &SigningKeyDescriptor) -> MindResult<()> {
        self.validate_descriptor(descriptor)?;
        commit.verify_signature()?;
        let Some(signature) = &commit.signature else { return Err(MindError::CommitUnsigned { commit_id: commit.id }); };
        if signature.key_id != descriptor.key_id { return Err(MindError::SigningPolicyRejected { reason: format!("commit key `{}` does not match descriptor key `{}`", signature.key_id, descriptor.key_id) }); }
        if let Some(public_key_hex) = &descriptor.public_key_hex {
            if &signature.public_key_hex != public_key_hex { return Err(MindError::SigningPolicyRejected { reason: "commit public key does not match descriptor".to_owned() }); }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SigningStatus {
    pub signing_configured: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_key: Option<SigningKeyDescriptor>,
    pub policy: SigningPolicy,
    pub policy_valid: bool,
    #[serde(default)]
    pub notes: Vec<String>,
}

impl SigningStatus {
    #[must_use]
    pub fn unsigned(policy: SigningPolicy) -> Self { Self { signing_configured: false, active_key: None, policy, policy_valid: true, notes: vec!["no signing key configured".to_owned()] } }
    #[must_use]
    pub fn for_descriptor(policy: SigningPolicy, descriptor: SigningKeyDescriptor) -> Self {
        let mut notes = Vec::new();
        let policy_valid = match policy.validate_descriptor(&descriptor) { Ok(()) => true, Err(error) => { notes.push(error.to_string()); false } };
        Self { signing_configured: true, active_key: Some(descriptor), policy, policy_valid, notes }
    }
}
