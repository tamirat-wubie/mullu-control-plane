use crate::{hash_serializable, EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum SecretManagerBackend {
    Environment,
    KubernetesSecret,
    AwsSecretsManager,
    GcpSecretManager,
    AzureKeyVault,
    HashicorpVault,
    ExternalGateway,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum SecretAccessMode {
    #[default]
    PlanOnly,
    DryRun,
    ReadApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum SecretAccessStatus {
    Planned,
    DryRunAccepted,
    Resolved,
    Rejected,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubAppJwtStatus {
    Planned,
    DryRunAccepted,
    Signed,
    Rejected,
}

const SENSITIVE_KEY_TERMS: &[&str] = &[
    "secret",
    "token",
    "credential",
    "password",
    "private_key",
    "api_key",
    "api-key",
    "apikey",
    "access_key",
    "refresh_token",
    "access_token",
    "authorization",
    "jwt",
];

const SAFE_REFERENCE_KEY_TERMS: &[&str] = &[
    "hash",
    "fingerprint",
    "digest",
    "ref",
    "reference",
    "id",
    "version",
    "status",
    "kind",
    "scope",
    "locator",
    "response_hash",
    "response",
    "receipt",
    "plan",
    "mode",
];

fn key_has_sensitive_term(key: &str) -> bool {
    let lower = key.to_ascii_lowercase();
    SENSITIVE_KEY_TERMS.iter().any(|term| lower.contains(term))
}

fn key_is_safe_reference(key: &str) -> bool {
    let lower = key.to_ascii_lowercase();
    SAFE_REFERENCE_KEY_TERMS
        .iter()
        .any(|term| lower.contains(term))
}

fn value_resembles_raw_secret(value: &str) -> bool {
    let trimmed = value.trim();
    let lower = trimmed.to_ascii_lowercase();
    !trimmed.is_empty()
        && (trimmed.contains("-----BEGIN ") && trimmed.contains("PRIVATE KEY-----")
            || trimmed.contains("ghp_")
            || trimmed.contains("github_pat_")
            || lower.contains("bearer ghp_")
            || lower.contains("bearer github_pat_")
            || lower.contains("xoxb-")
            || lower.contains("xoxa-")
            || lower.contains("xoxp-")
            || lower.contains("xoxr-")
            || lower.contains("ya29.")
            || (trimmed.starts_with("sk-") && trimmed.len() >= 20)
            || (lower.contains("bearer sk-") && trimmed.len() >= 27))
}

fn ensure_secret_safe_string(context: &str, path: &str, key: &str, value: &str) -> MindResult<()> {
    if value_resembles_raw_secret(value) {
        return Err(MindError::Store(format!(
            "{context} contains raw secret material at {path}"
        )));
    }
    if !value.is_empty() && key_has_sensitive_term(key) && !key_is_safe_reference(key) {
        return Err(MindError::Store(format!(
            "{context} contains direct sensitive field at {path}"
        )));
    }
    Ok(())
}

fn ensure_secret_safe_json_path(
    context: &str,
    path: &str,
    key: &str,
    value: &Value,
) -> MindResult<()> {
    match value {
        Value::Object(map) => {
            for (child_key, child_value) in map {
                let child_path = if path.is_empty() {
                    child_key.clone()
                } else {
                    format!("{path}.{child_key}")
                };
                ensure_secret_safe_json_path(context, &child_path, child_key, child_value)?;
            }
        }
        Value::Array(values) => {
            for (index, child_value) in values.iter().enumerate() {
                let child_path = format!("{path}[{index}]");
                ensure_secret_safe_json_path(context, &child_path, key, child_value)?;
            }
        }
        Value::String(text) => ensure_secret_safe_string(context, path, key, text)?,
        _ => {}
    }
    Ok(())
}

pub(crate) fn ensure_secret_safe_json_value(context: &str, value: &Value) -> MindResult<()> {
    ensure_secret_safe_json_path(context, "", "", value)
}

pub(crate) fn ensure_secret_safe_serialized<T: Serialize>(
    context: &str,
    value: &T,
) -> MindResult<()> {
    let serialized = serde_json::to_value(value)?;
    ensure_secret_safe_json_value(context, &serialized)
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SecretReference {
    pub backend: SecretManagerBackend,
    pub locator: String,
    pub key_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl SecretReference {
    pub fn new(
        backend: SecretManagerBackend,
        locator: impl Into<String>,
        key_id: impl Into<String>,
    ) -> MindResult<Self> {
        let locator = locator.into();
        let key_id = key_id.into();
        if locator.trim().is_empty() || key_id.trim().is_empty() {
            return Err(MindError::Store(
                "secret reference requires locator and key_id".to_owned(),
            ));
        }
        Ok(Self {
            backend,
            locator,
            key_id,
            version: None,
            metadata: BTreeMap::new(),
        })
    }

    #[must_use]
    pub fn with_version(mut self, version: impl Into<String>) -> Self {
        self.version = Some(version.into());
        self
    }

    #[must_use]
    pub fn with_metadata(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.metadata.insert(key.into(), value.into());
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SecretAccessPlan {
    pub plan_id: EventId,
    pub reference: SecretReference,
    pub purpose: String,
    pub mode: SecretAccessMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub allowed_fingerprint: Option<String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl SecretAccessPlan {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("secret access plan", self)?;
        if self.purpose.trim().is_empty() {
            return Err(MindError::Store(
                "secret access purpose is required".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.plan_id,
            &self.reference,
            &self.purpose,
            self.mode,
            &self.allowed_fingerprint,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "secret access plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SecretAccessReceipt {
    pub receipt_id: EventId,
    pub plan_id: EventId,
    pub backend: SecretManagerBackend,
    pub status: SecretAccessStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub secret_version: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub material_fingerprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
    pub receipt_hash: String,
    pub resolved_at: OffsetDateTime,
}

impl SecretAccessReceipt {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("secret access receipt", self)?;
        let expected = hash_serializable(&(
            self.receipt_id,
            self.plan_id,
            self.backend,
            self.status,
            &self.secret_version,
            &self.material_fingerprint,
            &self.response_hash,
            &self.attributes,
            self.resolved_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "secret access receipt hash mismatch".to_owned(),
            ));
        }
        if self.status == SecretAccessStatus::Resolved && self.material_fingerprint.is_none() {
            return Err(MindError::Store(
                "resolved secret access requires material fingerprint".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubAppJwtPlan {
    pub jwt_plan_id: EventId,
    pub app_id: u64,
    pub installation_id: u64,
    pub key_id: String,
    pub secret_plan_id: EventId,
    pub algorithm: String,
    pub issuer: String,
    pub audience: String,
    pub ttl_seconds: i64,
    pub mode: SecretAccessMode,
    pub claims_hash: String,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubAppJwtPlan {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub App JWT plan", self)?;
        if self.app_id == 0 || self.installation_id == 0 || self.key_id.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub App JWT plan requires app, installation and key id".to_owned(),
            ));
        }
        if self.ttl_seconds <= 0 || self.ttl_seconds > 600 {
            return Err(MindError::Store(
                "GitHub App JWT ttl must be in 1..=600 seconds".to_owned(),
            ));
        }
        let expected_claims = hash_serializable(&(
            self.app_id,
            &self.issuer,
            &self.audience,
            self.ttl_seconds,
            self.created_at.unix_timestamp(),
        ))?;
        if expected_claims != self.claims_hash {
            return Err(MindError::Store(
                "GitHub App JWT claims hash mismatch".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.jwt_plan_id,
            self.app_id,
            self.installation_id,
            &self.key_id,
            self.secret_plan_id,
            &self.algorithm,
            &self.issuer,
            &self.audience,
            self.ttl_seconds,
            self.mode,
            &self.claims_hash,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "GitHub App JWT plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubAppJwtReceipt {
    pub receipt_id: EventId,
    pub jwt_plan_id: EventId,
    pub secret_receipt_id: EventId,
    pub status: GitHubAppJwtStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub jwt_fingerprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<OffsetDateTime>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signer_response_hash: Option<String>,
    pub receipt_hash: String,
    pub signed_at: OffsetDateTime,
}

impl GitHubAppJwtReceipt {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub App JWT receipt", self)?;
        let expected = hash_serializable(&(
            self.receipt_id,
            self.jwt_plan_id,
            self.secret_receipt_id,
            self.status,
            &self.jwt_fingerprint,
            &self.expires_at,
            &self.signer_response_hash,
            self.signed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "GitHub App JWT receipt hash mismatch".to_owned(),
            ));
        }
        if self.status == GitHubAppJwtStatus::Signed && self.jwt_fingerprint.is_none() {
            return Err(MindError::Store(
                "signed GitHub App JWT receipt requires JWT fingerprint".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_secret_access(
    reference: SecretReference,
    purpose: impl Into<String>,
    mode: SecretAccessMode,
    allowed_fingerprint: Option<String>,
) -> MindResult<SecretAccessPlan> {
    let purpose = purpose.into();
    if purpose.trim().is_empty() {
        return Err(MindError::Store(
            "secret access purpose is required".to_owned(),
        ));
    }
    let plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        plan_id,
        &reference,
        &purpose,
        mode,
        &allowed_fingerprint,
        created_at,
    ))?;
    let plan = SecretAccessPlan {
        plan_id,
        reference,
        purpose,
        mode,
        allowed_fingerprint,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_secret_access_receipt(
    plan: &SecretAccessPlan,
    material_fingerprint: Option<String>,
    secret_version: Option<String>,
    response_metadata: BTreeMap<String, String>,
) -> MindResult<SecretAccessReceipt> {
    plan.verify()?;
    if let (Some(expected), Some(actual)) = (&plan.allowed_fingerprint, &material_fingerprint) {
        if expected != actual {
            return Err(MindError::Store(
                "secret fingerprint does not match access plan".to_owned(),
            ));
        }
    }
    let status = match plan.mode {
        SecretAccessMode::PlanOnly => SecretAccessStatus::Planned,
        SecretAccessMode::DryRun => SecretAccessStatus::DryRunAccepted,
        SecretAccessMode::ReadApproved => {
            if material_fingerprint.is_some() {
                SecretAccessStatus::Resolved
            } else {
                SecretAccessStatus::Rejected
            }
        }
    };
    let receipt_id = EventId::new();
    let resolved_at = OffsetDateTime::now_utc();
    let response_hash = if response_metadata.is_empty() {
        None
    } else {
        Some(hash_serializable(&response_metadata)?)
    };
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.plan_id,
        plan.reference.backend,
        status,
        &secret_version,
        &material_fingerprint,
        &response_hash,
        &response_metadata,
        resolved_at,
    ))?;
    let receipt = SecretAccessReceipt {
        receipt_id,
        plan_id: plan.plan_id,
        backend: plan.reference.backend,
        status,
        secret_version,
        material_fingerprint,
        response_hash,
        attributes: response_metadata,
        receipt_hash,
        resolved_at,
    };
    receipt.verify()?;
    Ok(receipt)
}

pub fn plan_github_app_jwt_from_secret(
    app_id: u64,
    installation_id: u64,
    secret_plan: &SecretAccessPlan,
    ttl_seconds: i64,
) -> MindResult<GitHubAppJwtPlan> {
    secret_plan.verify()?;
    let jwt_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let issuer = app_id.to_string();
    let audience = "github-app-installation-token".to_owned();
    let algorithm = "RS256".to_owned();
    let claims_hash = hash_serializable(&(
        app_id,
        &issuer,
        &audience,
        ttl_seconds,
        created_at.unix_timestamp(),
    ))?;
    let plan_hash = hash_serializable(&(
        jwt_plan_id,
        app_id,
        installation_id,
        &secret_plan.reference.key_id,
        secret_plan.plan_id,
        &algorithm,
        &issuer,
        &audience,
        ttl_seconds,
        secret_plan.mode,
        &claims_hash,
        created_at,
    ))?;
    let plan = GitHubAppJwtPlan {
        jwt_plan_id,
        app_id,
        installation_id,
        key_id: secret_plan.reference.key_id.clone(),
        secret_plan_id: secret_plan.plan_id,
        algorithm,
        issuer,
        audience,
        ttl_seconds,
        mode: secret_plan.mode,
        claims_hash,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_github_app_jwt_receipt(
    plan: &GitHubAppJwtPlan,
    secret_receipt: &SecretAccessReceipt,
    jwt_fingerprint: Option<String>,
    signer_response_hash: Option<String>,
) -> MindResult<GitHubAppJwtReceipt> {
    plan.verify()?;
    secret_receipt.verify()?;
    if plan.secret_plan_id != secret_receipt.plan_id {
        return Err(MindError::Store(
            "GitHub App JWT secret receipt does not match plan".to_owned(),
        ));
    }
    let status = match plan.mode {
        SecretAccessMode::PlanOnly => GitHubAppJwtStatus::Planned,
        SecretAccessMode::DryRun => GitHubAppJwtStatus::DryRunAccepted,
        SecretAccessMode::ReadApproved => {
            if secret_receipt.status == SecretAccessStatus::Resolved && jwt_fingerprint.is_some() {
                GitHubAppJwtStatus::Signed
            } else {
                GitHubAppJwtStatus::Rejected
            }
        }
    };
    let receipt_id = EventId::new();
    let signed_at = OffsetDateTime::now_utc();
    let expires_at = if matches!(
        status,
        GitHubAppJwtStatus::Signed | GitHubAppJwtStatus::DryRunAccepted
    ) {
        Some(signed_at + Duration::seconds(plan.ttl_seconds))
    } else {
        None
    };
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.jwt_plan_id,
        secret_receipt.receipt_id,
        status,
        &jwt_fingerprint,
        &expires_at,
        &signer_response_hash,
        signed_at,
    ))?;
    let receipt = GitHubAppJwtReceipt {
        receipt_id,
        jwt_plan_id: plan.jwt_plan_id,
        secret_receipt_id: secret_receipt.receipt_id,
        status,
        jwt_fingerprint,
        expires_at,
        signer_response_hash,
        receipt_hash,
        signed_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
