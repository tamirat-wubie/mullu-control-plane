use crate::secret_manager_jwt::ensure_secret_safe_serialized;
use crate::{
    hash_serializable, EventId, GitHubAppInstallationTokenReceipt, GitHubAppJwtReceipt,
    GitHubAppTokenStatus, LiveSecretConnectorReceipt, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum GitHubTokenExchangeWorkerMode {
    #[default]
    PlanOnly,
    DryRun,
    ExchangeApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubTokenExchangeWorkerStatus {
    Planned,
    DryRunAccepted,
    TokenIssued,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubTokenExchangeWorkerPlan {
    pub exchange_plan_id: EventId,
    pub repository: String,
    pub installation_id: u64,
    pub jwt_receipt_id: EventId,
    pub secret_connector_receipt_id: EventId,
    pub mode: GitHubTokenExchangeWorkerMode,
    pub permissions_hash: String,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubTokenExchangeWorkerPlan {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub token exchange worker plan", self)?;
        if self.repository.trim().is_empty()
            || self.installation_id == 0
            || self.permissions_hash.trim().is_empty()
        {
            return Err(MindError::Store(
                "GitHub token exchange plan requires repository, installation and permissions hash"
                    .to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.exchange_plan_id,
            &self.repository,
            self.installation_id,
            self.jwt_receipt_id,
            self.secret_connector_receipt_id,
            self.mode,
            &self.permissions_hash,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "GitHub token exchange plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubTokenExchangeWorkerReceipt {
    pub exchange_receipt_id: EventId,
    pub exchange_plan_id: EventId,
    pub token_receipt_id: EventId,
    pub installation_id: u64,
    pub status: GitHubTokenExchangeWorkerStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub token_fingerprint: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_response_hash: Option<String>,
    pub receipt_hash: String,
    pub exchanged_at: OffsetDateTime,
}

impl GitHubTokenExchangeWorkerReceipt {
    pub fn verify(&self) -> MindResult<()> {
        ensure_secret_safe_serialized("GitHub token exchange worker receipt", self)?;
        if self.status == GitHubTokenExchangeWorkerStatus::TokenIssued
            && self.token_fingerprint.is_none()
        {
            return Err(MindError::Store(
                "GitHub token exchange receipt requires token fingerprint".to_owned(),
            ));
        }
        let expected = hash_serializable(&(
            self.exchange_receipt_id,
            self.exchange_plan_id,
            self.token_receipt_id,
            self.installation_id,
            self.status,
            &self.token_fingerprint,
            &self.provider_response_hash,
            self.exchanged_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "GitHub token exchange receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_github_token_exchange_worker(
    repository: impl Into<String>,
    installation_id: u64,
    jwt_receipt: &GitHubAppJwtReceipt,
    secret_connector: &LiveSecretConnectorReceipt,
    mode: GitHubTokenExchangeWorkerMode,
    permissions_hash: impl Into<String>,
) -> MindResult<GitHubTokenExchangeWorkerPlan> {
    jwt_receipt.verify()?;
    secret_connector.verify()?;
    let repository = repository.into();
    let permissions_hash = permissions_hash.into();
    let exchange_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        exchange_plan_id,
        &repository,
        installation_id,
        jwt_receipt.receipt_id,
        secret_connector.connector_receipt_id,
        mode,
        &permissions_hash,
        created_at,
    ))?;
    let plan = GitHubTokenExchangeWorkerPlan {
        exchange_plan_id,
        repository,
        installation_id,
        jwt_receipt_id: jwt_receipt.receipt_id,
        secret_connector_receipt_id: secret_connector.connector_receipt_id,
        mode,
        permissions_hash,
        plan_hash,
        created_at,
    };
    plan.verify()?;
    Ok(plan)
}

pub fn record_github_token_exchange_worker_receipt(
    plan: &GitHubTokenExchangeWorkerPlan,
    token_receipt: &GitHubAppInstallationTokenReceipt,
) -> MindResult<GitHubTokenExchangeWorkerReceipt> {
    plan.verify()?;
    token_receipt.verify()?;
    if token_receipt.installation_id != plan.installation_id {
        return Err(MindError::Store(
            "GitHub token receipt installation does not match exchange plan".to_owned(),
        ));
    }
    let status = match token_receipt.status {
        GitHubAppTokenStatus::Issued => GitHubTokenExchangeWorkerStatus::TokenIssued,
        GitHubAppTokenStatus::DryRunAccepted => GitHubTokenExchangeWorkerStatus::DryRunAccepted,
        GitHubAppTokenStatus::Planned => GitHubTokenExchangeWorkerStatus::Planned,
        GitHubAppTokenStatus::Rejected => GitHubTokenExchangeWorkerStatus::Rejected,
    };
    let exchange_receipt_id = EventId::new();
    let exchanged_at = OffsetDateTime::now_utc();
    let token_fingerprint = token_receipt.token_fingerprint.clone();
    let provider_response_hash = token_receipt.response_hash.clone();
    let receipt_hash = hash_serializable(&(
        exchange_receipt_id,
        plan.exchange_plan_id,
        token_receipt.receipt_id,
        plan.installation_id,
        status,
        &token_fingerprint,
        &provider_response_hash,
        exchanged_at,
    ))?;
    let receipt = GitHubTokenExchangeWorkerReceipt {
        exchange_receipt_id,
        exchange_plan_id: plan.exchange_plan_id,
        token_receipt_id: token_receipt.receipt_id,
        installation_id: plan.installation_id,
        status,
        token_fingerprint,
        provider_response_hash,
        receipt_hash,
        exchanged_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
