use crate::{
    evaluate_branch_protection_policy, hash_serializable, BranchProtectionEvaluationReport,
    BranchProtectionObservedState, BranchProtectionPolicy, EventId, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum BranchProtectionReconcileMode {
    #[default]
    PlanOnly,
    DryRun,
    ApplyApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum BranchProtectionReconcileStatus {
    Noop,
    Planned,
    DryRunAccepted,
    Applied,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct BranchProtectionReconcilePlan {
    pub reconcile_id: EventId,
    pub policy: BranchProtectionPolicy,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub observed: Option<BranchProtectionObservedState>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub evaluation: Option<BranchProtectionEvaluationReport>,
    pub mode: BranchProtectionReconcileMode,
    #[serde(default)]
    pub drift: Vec<String>,
    #[serde(default)]
    pub actions: Vec<String>,
    pub rest_endpoint: String,
    pub rest_payload: Value,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl BranchProtectionReconcilePlan {
    pub fn verify(&self) -> MindResult<()> {
        self.policy.verify()?;
        if let Some(evaluation) = &self.evaluation {
            evaluation.verify()?;
        }
        let expected = hash_serializable(&(
            self.reconcile_id,
            &self.policy,
            &self.observed,
            &self.evaluation,
            self.mode,
            &self.drift,
            &self.actions,
            &self.rest_endpoint,
            &self.rest_payload,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "branch protection reconcile plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BranchProtectionReconcileReceipt {
    pub receipt_id: EventId,
    pub reconcile_id: EventId,
    pub policy_id: EventId,
    pub repository: String,
    pub branch: String,
    pub status: BranchProtectionReconcileStatus,
    #[serde(default)]
    pub applied_actions: Vec<String>,
    #[serde(default)]
    pub findings: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    pub receipt_hash: String,
    pub reconciled_at: OffsetDateTime,
}

impl BranchProtectionReconcileReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.reconcile_id,
            self.policy_id,
            &self.repository,
            &self.branch,
            self.status,
            &self.applied_actions,
            &self.findings,
            &self.response_hash,
            self.reconciled_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "branch protection reconcile receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_branch_protection_reconcile(
    policy: BranchProtectionPolicy,
    observed: Option<BranchProtectionObservedState>,
    mode: BranchProtectionReconcileMode,
) -> MindResult<BranchProtectionReconcilePlan> {
    policy.verify()?;
    let evaluation = observed
        .clone()
        .map(|state| evaluate_branch_protection_policy(&policy, state))
        .transpose()?;
    let mut drift = evaluation
        .as_ref()
        .map(|report| report.findings.clone())
        .unwrap_or_default();
    if observed.is_none() {
        drift.push("observed branch protection state missing; create/update required".to_owned());
    }
    let actions = if drift.is_empty() {
        vec!["noop: observed protection already satisfies policy".to_owned()]
    } else {
        vec![
            "put_branch_protection".to_owned(),
            "verify_branch_protection_after_apply".to_owned(),
        ]
    };
    let (owner, repo) = split_repository(&policy.repository)?;
    let rest_endpoint = format!(
        "/repos/{owner}/{repo}/branches/{}/protection",
        policy.branch
    );
    let rest_payload = github_branch_protection_payload(&policy);
    let reconcile_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        reconcile_id,
        &policy,
        &observed,
        &evaluation,
        mode,
        &drift,
        &actions,
        &rest_endpoint,
        &rest_payload,
        created_at,
    ))?;
    Ok(BranchProtectionReconcilePlan {
        reconcile_id,
        policy,
        observed,
        evaluation,
        mode,
        drift,
        actions,
        rest_endpoint,
        rest_payload,
        plan_hash,
        created_at,
    })
}

pub fn record_branch_protection_reconcile_receipt(
    plan: &BranchProtectionReconcilePlan,
    response_payload: Option<Value>,
) -> MindResult<BranchProtectionReconcileReceipt> {
    plan.verify()?;
    let response_hash = response_payload
        .as_ref()
        .map(hash_serializable)
        .transpose()?;
    let findings = if plan.drift.is_empty() {
        vec!["no drift detected".to_owned()]
    } else {
        plan.drift.clone()
    };
    let status = match plan.mode {
        BranchProtectionReconcileMode::PlanOnly => {
            if plan.drift.is_empty() {
                BranchProtectionReconcileStatus::Noop
            } else {
                BranchProtectionReconcileStatus::Planned
            }
        }
        BranchProtectionReconcileMode::DryRun => BranchProtectionReconcileStatus::DryRunAccepted,
        BranchProtectionReconcileMode::ApplyApproved => {
            if response_hash.is_some() {
                BranchProtectionReconcileStatus::Applied
            } else {
                BranchProtectionReconcileStatus::Rejected
            }
        }
    };
    let applied_actions = if matches!(
        status,
        BranchProtectionReconcileStatus::Applied | BranchProtectionReconcileStatus::DryRunAccepted
    ) {
        plan.actions.clone()
    } else {
        Vec::new()
    };
    let receipt_id = EventId::new();
    let reconciled_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.reconcile_id,
        plan.policy.policy_id,
        &plan.policy.repository,
        &plan.policy.branch,
        status,
        &applied_actions,
        &findings,
        &response_hash,
        reconciled_at,
    ))?;
    Ok(BranchProtectionReconcileReceipt {
        receipt_id,
        reconcile_id: plan.reconcile_id,
        policy_id: plan.policy.policy_id,
        repository: plan.policy.repository.clone(),
        branch: plan.policy.branch.clone(),
        status,
        applied_actions,
        findings,
        response_hash,
        receipt_hash,
        reconciled_at,
    })
}

#[must_use]
pub fn github_branch_protection_payload(policy: &BranchProtectionPolicy) -> Value {
    let checks = policy
        .required_status_checks
        .iter()
        .map(|name| json!({ "context": name }))
        .collect::<Vec<_>>();
    json!({
        "required_status_checks": if policy.require_status_checks {
            json!({ "strict": true, "checks": checks })
        } else { Value::Null },
        "enforce_admins": policy.enforce_admins,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": policy.review_policy.dismiss_stale_reviews,
            "require_code_owner_reviews": policy.review_policy.require_code_owner_reviews,
            "required_approving_review_count": policy.review_policy.required_approving_review_count,
            "require_last_push_approval": policy.review_policy.require_last_push_approval,
        },
        "restrictions": Value::Null,
        "required_linear_history": policy.require_linear_history,
        "allow_force_pushes": false,
        "allow_deletions": false,
        "block_creations": false,
        "required_conversation_resolution": policy.require_conversation_resolution,
        "lock_branch": false,
        "allow_fork_syncing": true,
    })
}

fn split_repository(repository: &str) -> MindResult<(&str, &str)> {
    let Some((owner, repo)) = repository.split_once('/') else {
        return Err(MindError::Store(
            "GitHub repository must be formatted as owner/repo".to_owned(),
        ));
    };
    if owner.trim().is_empty() || repo.trim().is_empty() {
        return Err(MindError::Store(
            "GitHub repository must include owner and repo".to_owned(),
        ));
    }
    Ok((owner, repo))
}
