use crate::secret_manager_jwt::ensure_secret_safe_serialized;
use crate::{hash_serializable, EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use time::{Duration, OffsetDateTime};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum GitHubAppTokenMode {
    #[default]
    PlanOnly,
    DryRun,
    ExchangeApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubAppTokenStatus {
    Planned,
    DryRunAccepted,
    Issued,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubAppInstallationTokenRequest {
    pub request_id: EventId,
    pub app_id: u64,
    pub installation_id: u64,
    pub repository: String,
    #[serde(default)]
    pub permissions: BTreeMap<String, String>,
    #[serde(default)]
    pub repositories: Vec<String>,
    pub private_key_fingerprint: String,
    pub token_ttl_seconds: i64,
    pub request_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubAppInstallationTokenRequest {
    pub fn new(
        app_id: u64,
        installation_id: u64,
        repository: impl Into<String>,
        private_key_fingerprint: impl Into<String>,
        mut permissions: BTreeMap<String, String>,
        repositories: Vec<String>,
        token_ttl_seconds: i64,
    ) -> MindResult<Self> {
        let repository = repository.into();
        let private_key_fingerprint = private_key_fingerprint.into();
        if app_id == 0 || installation_id == 0 {
            return Err(MindError::Store(
                "GitHub App token request requires non-zero app_id and installation_id".to_owned(),
            ));
        }
        if repository.trim().is_empty() || private_key_fingerprint.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub App token request requires repository and private key fingerprint"
                    .to_owned(),
            ));
        }
        if token_ttl_seconds <= 0 || token_ttl_seconds > 3600 {
            return Err(MindError::Store(
                "GitHub App token ttl must be in 1..=3600 seconds".to_owned(),
            ));
        }
        permissions
            .entry("checks".to_owned())
            .or_insert_with(|| "write".to_owned());
        permissions
            .entry("contents".to_owned())
            .or_insert_with(|| "read".to_owned());
        let request_id = EventId::new();
        let created_at = OffsetDateTime::now_utc();
        let request_hash = hash_serializable(&(
            request_id,
            app_id,
            installation_id,
            &repository,
            &permissions,
            &repositories,
            &private_key_fingerprint,
            token_ttl_seconds,
            created_at,
        ))?;
        Ok(Self {
            request_id,
            app_id,
            installation_id,
            repository,
            permissions,
            repositories,
            private_key_fingerprint,
            token_ttl_seconds,
            request_hash,
            created_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub App installation token request", self)?;
        let expected = hash_serializable(&(
            self.request_id,
            self.app_id,
            self.installation_id,
            &self.repository,
            &self.permissions,
            &self.repositories,
            &self.private_key_fingerprint,
            self.token_ttl_seconds,
            self.created_at,
        ))?;
        if expected != self.request_hash {
            return Err(MindError::Store(
                "GitHub App token request hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn rest_payload(&self) -> Value {
        let mut payload = json!({ "permissions": &self.permissions });
        if !self.repositories.is_empty() {
            payload["repositories"] = json!(&self.repositories);
        }
        payload
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct GitHubAppInstallationTokenPlan {
    pub plan_id: EventId,
    pub request: GitHubAppInstallationTokenRequest,
    pub mode: GitHubAppTokenMode,
    pub jwt_required: bool,
    pub rest_method: String,
    pub rest_endpoint: String,
    pub rest_payload: Value,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubAppInstallationTokenPlan {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub App installation token plan", self)?;
        self.request.verify()?;
        let expected = hash_serializable(&(
            self.plan_id,
            &self.request,
            self.mode,
            self.jwt_required,
            &self.rest_method,
            &self.rest_endpoint,
            &self.rest_payload,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "GitHub App token plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubAppInstallationTokenReceipt {
    pub receipt_id: EventId,
    pub plan_id: EventId,
    pub request_id: EventId,
    pub installation_id: u64,
    pub status: GitHubAppTokenStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub token_fingerprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expires_at: Option<OffsetDateTime>,
    #[serde(default)]
    pub permissions: BTreeMap<String, String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    pub receipt_hash: String,
    pub issued_at: OffsetDateTime,
}

impl GitHubAppInstallationTokenReceipt {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub App installation token receipt", self)?;
        let expected = hash_serializable(&(
            self.receipt_id,
            self.plan_id,
            self.request_id,
            self.installation_id,
            self.status,
            &self.token_fingerprint,
            &self.expires_at,
            &self.permissions,
            &self.response_hash,
            self.issued_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "GitHub App token receipt hash mismatch".to_owned(),
            ));
        }
        if self.status == GitHubAppTokenStatus::Issued && self.token_fingerprint.is_none() {
            return Err(MindError::Store(
                "issued GitHub App token receipt requires a token fingerprint".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_github_app_installation_token(
    request: GitHubAppInstallationTokenRequest,
    mode: GitHubAppTokenMode,
) -> MindResult<GitHubAppInstallationTokenPlan> {
    request.verify()?;
    let plan_id = EventId::new();
    let rest_endpoint = format!(
        "/app/installations/{}/access_tokens",
        request.installation_id
    );
    let rest_payload = request.rest_payload();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        plan_id,
        &request,
        mode,
        true,
        "POST",
        &rest_endpoint,
        &rest_payload,
        created_at,
    ))?;
    Ok(GitHubAppInstallationTokenPlan {
        plan_id,
        request,
        mode,
        jwt_required: true,
        rest_method: "POST".to_owned(),
        rest_endpoint,
        rest_payload,
        plan_hash,
        created_at,
    })
}

pub fn record_github_app_installation_token_receipt(
    plan: &GitHubAppInstallationTokenPlan,
    token_fingerprint: Option<String>,
    response: Option<&Value>,
) -> MindResult<GitHubAppInstallationTokenReceipt> {
    plan.verify()?;
    let issued_at = OffsetDateTime::now_utc();
    let status = match plan.mode {
        GitHubAppTokenMode::PlanOnly => GitHubAppTokenStatus::Planned,
        GitHubAppTokenMode::DryRun => GitHubAppTokenStatus::DryRunAccepted,
        GitHubAppTokenMode::ExchangeApproved => {
            if token_fingerprint
                .as_ref()
                .is_some_and(|value| !value.trim().is_empty())
            {
                GitHubAppTokenStatus::Issued
            } else {
                GitHubAppTokenStatus::Rejected
            }
        }
    };
    let expires_at = if status == GitHubAppTokenStatus::Issued {
        Some(issued_at + Duration::seconds(plan.request.token_ttl_seconds))
    } else {
        None
    };
    let response_hash = match response {
        Some(value) => Some(hash_serializable(value)?),
        None => None,
    };
    let receipt_id = EventId::new();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.plan_id,
        plan.request.request_id,
        plan.request.installation_id,
        status,
        &token_fingerprint,
        &expires_at,
        &plan.request.permissions,
        &response_hash,
        issued_at,
    ))?;
    let receipt = GitHubAppInstallationTokenReceipt {
        receipt_id,
        plan_id: plan.plan_id,
        request_id: plan.request.request_id,
        installation_id: plan.request.installation_id,
        status,
        token_fingerprint,
        expires_at,
        permissions: plan.request.permissions.clone(),
        response_hash,
        receipt_hash,
        issued_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
