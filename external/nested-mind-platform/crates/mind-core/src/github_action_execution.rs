use crate::{
    hash_serializable, BranchProtectionReconcilePlan, EventId, GitHubAppInstallationTokenPlan,
    GitHubAppInstallationTokenReceipt, GitHubAppTokenStatus, GitHubCheckRunWritePlan, MindError,
    MindResult,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubActionKind {
    CheckRunWrite,
    BranchProtectionReconcile,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum GitHubActionExecutionMode {
    #[default]
    PlanOnly,
    DryRun,
    ExecuteApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubActionExecutionStatus {
    Planned,
    DryRunAccepted,
    Executed,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct GitHubActionExecutionPlan {
    pub execution_id: EventId,
    pub token_plan_id: EventId,
    pub action_kind: GitHubActionKind,
    pub repository: String,
    pub rest_method: String,
    pub rest_endpoint: String,
    pub rest_payload: Value,
    pub action_hash: String,
    pub mode: GitHubActionExecutionMode,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubActionExecutionPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.execution_id,
            self.token_plan_id,
            self.action_kind,
            &self.repository,
            &self.rest_method,
            &self.rest_endpoint,
            &self.rest_payload,
            &self.action_hash,
            self.mode,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "GitHub action execution plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubActionExecutionReceipt {
    pub receipt_id: EventId,
    pub execution_id: EventId,
    pub token_receipt_id: EventId,
    pub action_kind: GitHubActionKind,
    pub repository: String,
    pub status: GitHubActionExecutionStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub http_status: Option<u16>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    pub receipt_hash: String,
    pub executed_at: OffsetDateTime,
}

impl GitHubActionExecutionReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.execution_id,
            self.token_receipt_id,
            self.action_kind,
            &self.repository,
            self.status,
            self.http_status,
            &self.response_hash,
            self.executed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "GitHub action execution receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

fn ensure_token_boundary(
    plan: &GitHubAppInstallationTokenPlan,
    repository: &str,
) -> MindResult<()> {
    plan.verify()?;
    if plan.request.repository != repository {
        return Err(MindError::Store(
            "GitHub token plan repository does not match action repository".to_owned(),
        ));
    }
    Ok(())
}

pub fn plan_github_check_run_action_execution(
    token_plan: &GitHubAppInstallationTokenPlan,
    check_plan: &GitHubCheckRunWritePlan,
    mode: GitHubActionExecutionMode,
) -> MindResult<GitHubActionExecutionPlan> {
    check_plan.verify()?;
    ensure_token_boundary(token_plan, &check_plan.request.repository)?;
    let execution_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let rest_payload = check_plan.rest_payload.clone();
    let plan_hash = hash_serializable(&(
        execution_id,
        token_plan.plan_id,
        GitHubActionKind::CheckRunWrite,
        &check_plan.request.repository,
        "POST",
        &check_plan.rest_endpoint,
        &rest_payload,
        &check_plan.plan_hash,
        mode,
        created_at,
    ))?;
    Ok(GitHubActionExecutionPlan {
        execution_id,
        token_plan_id: token_plan.plan_id,
        action_kind: GitHubActionKind::CheckRunWrite,
        repository: check_plan.request.repository.clone(),
        rest_method: "POST".to_owned(),
        rest_endpoint: check_plan.rest_endpoint.clone(),
        rest_payload,
        action_hash: check_plan.plan_hash.clone(),
        mode,
        plan_hash,
        created_at,
    })
}

pub fn plan_branch_protection_action_execution(
    token_plan: &GitHubAppInstallationTokenPlan,
    reconcile_plan: &BranchProtectionReconcilePlan,
    mode: GitHubActionExecutionMode,
) -> MindResult<GitHubActionExecutionPlan> {
    reconcile_plan.verify()?;
    ensure_token_boundary(token_plan, &reconcile_plan.policy.repository)?;
    let execution_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        execution_id,
        token_plan.plan_id,
        GitHubActionKind::BranchProtectionReconcile,
        &reconcile_plan.policy.repository,
        "PUT",
        &reconcile_plan.rest_endpoint,
        &reconcile_plan.rest_payload,
        &reconcile_plan.plan_hash,
        mode,
        created_at,
    ))?;
    Ok(GitHubActionExecutionPlan {
        execution_id,
        token_plan_id: token_plan.plan_id,
        action_kind: GitHubActionKind::BranchProtectionReconcile,
        repository: reconcile_plan.policy.repository.clone(),
        rest_method: "PUT".to_owned(),
        rest_endpoint: reconcile_plan.rest_endpoint.clone(),
        rest_payload: reconcile_plan.rest_payload.clone(),
        action_hash: reconcile_plan.plan_hash.clone(),
        mode,
        plan_hash,
        created_at,
    })
}

pub fn record_github_action_execution_receipt(
    plan: &GitHubActionExecutionPlan,
    token_receipt: &GitHubAppInstallationTokenReceipt,
    http_status: Option<u16>,
    response: Option<&Value>,
) -> MindResult<GitHubActionExecutionReceipt> {
    plan.verify()?;
    token_receipt.verify()?;
    let token_usable = token_receipt.status == GitHubAppTokenStatus::Issued;
    let status = match plan.mode {
        GitHubActionExecutionMode::PlanOnly => GitHubActionExecutionStatus::Planned,
        GitHubActionExecutionMode::DryRun => GitHubActionExecutionStatus::DryRunAccepted,
        GitHubActionExecutionMode::ExecuteApproved => {
            if token_usable && http_status.is_some_and(|code| (200..300).contains(&code)) {
                GitHubActionExecutionStatus::Executed
            } else {
                GitHubActionExecutionStatus::Rejected
            }
        }
    };
    let response_hash = match response {
        Some(value) => Some(hash_serializable(value)?),
        None => None,
    };
    let receipt_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.execution_id,
        token_receipt.receipt_id,
        plan.action_kind,
        &plan.repository,
        status,
        http_status,
        &response_hash,
        executed_at,
    ))?;
    let receipt = GitHubActionExecutionReceipt {
        receipt_id,
        execution_id: plan.execution_id,
        token_receipt_id: token_receipt.receipt_id,
        action_kind: plan.action_kind,
        repository: plan.repository.clone(),
        status,
        http_status,
        response_hash,
        receipt_hash,
        executed_at,
    };
    receipt.verify()?;
    Ok(receipt)
}
