use crate::{hash_serializable, EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BranchProtectionReviewPolicy {
    pub required_approving_review_count: u8,
    pub require_code_owner_reviews: bool,
    pub dismiss_stale_reviews: bool,
    pub require_last_push_approval: bool,
}

impl Default for BranchProtectionReviewPolicy {
    fn default() -> Self {
        Self {
            required_approving_review_count: 2,
            require_code_owner_reviews: true,
            dismiss_stale_reviews: true,
            require_last_push_approval: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BranchProtectionPolicy {
    pub policy_id: EventId,
    pub repository: String,
    pub branch: String,
    pub enforce_admins: bool,
    pub require_linear_history: bool,
    pub require_conversation_resolution: bool,
    pub require_signed_commits: bool,
    pub require_status_checks: bool,
    #[serde(default)]
    pub required_status_checks: BTreeSet<String>,
    pub review_policy: BranchProtectionReviewPolicy,
    pub policy_hash: String,
    pub created_at: OffsetDateTime,
}

impl BranchProtectionPolicy {
    pub fn new(
        repository: impl Into<String>,
        branch: impl Into<String>,
        required_status_checks: BTreeSet<String>,
    ) -> MindResult<Self> {
        let repository = repository.into();
        let branch = branch.into();
        if repository.trim().is_empty() || branch.trim().is_empty() {
            return Err(MindError::Store(
                "branch protection policy requires repository and branch".to_owned(),
            ));
        }
        let policy_id = EventId::new();
        let created_at = OffsetDateTime::now_utc();
        let review_policy = BranchProtectionReviewPolicy::default();
        let policy = Self {
            policy_id,
            repository,
            branch,
            enforce_admins: true,
            require_linear_history: true,
            require_conversation_resolution: true,
            require_signed_commits: false,
            require_status_checks: true,
            required_status_checks,
            review_policy,
            policy_hash: String::new(),
            created_at,
        };
        policy.with_hash()
    }

    fn with_hash(mut self) -> MindResult<Self> {
        self.policy_hash = hash_serializable(&(
            self.policy_id,
            &self.repository,
            &self.branch,
            self.enforce_admins,
            self.require_linear_history,
            self.require_conversation_resolution,
            self.require_signed_commits,
            self.require_status_checks,
            &self.required_status_checks,
            &self.review_policy,
            self.created_at,
        ))?;
        Ok(self)
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.policy_id,
            &self.repository,
            &self.branch,
            self.enforce_admins,
            self.require_linear_history,
            self.require_conversation_resolution,
            self.require_signed_commits,
            self.require_status_checks,
            &self.required_status_checks,
            &self.review_policy,
            self.created_at,
        ))?;
        if expected != self.policy_hash {
            return Err(MindError::Store(
                "branch protection policy hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn to_github_rest_payload(&self) -> Value {
        let checks = self
            .required_status_checks
            .iter()
            .map(|context| json!({ "context": context }))
            .collect::<Vec<_>>();
        json!({
            "required_status_checks": {
                "strict": true,
                "checks": checks
            },
            "enforce_admins": self.enforce_admins,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": self.review_policy.dismiss_stale_reviews,
                "require_code_owner_reviews": self.review_policy.require_code_owner_reviews,
                "required_approving_review_count": self.review_policy.required_approving_review_count,
                "require_last_push_approval": self.review_policy.require_last_push_approval
            },
            "restrictions": null,
            "required_linear_history": self.require_linear_history,
            "required_conversation_resolution": self.require_conversation_resolution,
            "required_signatures": self.require_signed_commits,
            "allow_force_pushes": false,
            "allow_deletions": false,
            "block_creations": true,
            "required_deployments": null,
            "lock_branch": false,
            "allow_fork_syncing": true
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BranchProtectionObservedState {
    #[serde(default)]
    pub required_status_checks: BTreeSet<String>,
    pub enforce_admins: bool,
    pub required_approving_review_count: u8,
    pub require_code_owner_reviews: bool,
    pub require_conversation_resolution: bool,
    pub require_linear_history: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct BranchProtectionEvaluationReport {
    pub report_id: EventId,
    pub policy_id: EventId,
    pub repository: String,
    pub branch: String,
    #[serde(default)]
    pub missing_required_checks: BTreeSet<String>,
    #[serde(default)]
    pub extra_required_checks: BTreeSet<String>,
    #[serde(default)]
    pub findings: Vec<String>,
    pub compliant: bool,
    pub github_payload: Value,
    pub report_hash: String,
    pub evaluated_at: OffsetDateTime,
}

impl BranchProtectionEvaluationReport {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.report_id,
            self.policy_id,
            &self.repository,
            &self.branch,
            &self.missing_required_checks,
            &self.extra_required_checks,
            &self.findings,
            self.compliant,
            &self.github_payload,
            self.evaluated_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "branch protection evaluation hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn production_branch_protection_policy(
    repository: impl Into<String>,
    branch: impl Into<String>,
) -> MindResult<BranchProtectionPolicy> {
    BranchProtectionPolicy::new(repository, branch, crate::required_readiness_check_names())
}

pub fn evaluate_branch_protection_policy(
    policy: &BranchProtectionPolicy,
    observed: BranchProtectionObservedState,
) -> MindResult<BranchProtectionEvaluationReport> {
    policy.verify()?;
    let missing_required_checks = policy
        .required_status_checks
        .difference(&observed.required_status_checks)
        .cloned()
        .collect::<BTreeSet<_>>();
    let extra_required_checks = observed
        .required_status_checks
        .difference(&policy.required_status_checks)
        .cloned()
        .collect::<BTreeSet<_>>();
    let mut findings = Vec::new();
    if !missing_required_checks.is_empty() {
        findings.push(format!(
            "missing required status checks: {:?}",
            missing_required_checks
        ));
    }
    if !observed.enforce_admins && policy.enforce_admins {
        findings.push("admin enforcement is disabled".to_owned());
    }
    if observed.required_approving_review_count
        < policy.review_policy.required_approving_review_count
    {
        findings.push(format!(
            "only {} approving reviews required; policy requires {}",
            observed.required_approving_review_count,
            policy.review_policy.required_approving_review_count
        ));
    }
    if policy.review_policy.require_code_owner_reviews && !observed.require_code_owner_reviews {
        findings.push("code owner review requirement is disabled".to_owned());
    }
    if policy.require_conversation_resolution && !observed.require_conversation_resolution {
        findings.push("conversation resolution requirement is disabled".to_owned());
    }
    if policy.require_linear_history && !observed.require_linear_history {
        findings.push("linear history requirement is disabled".to_owned());
    }
    let compliant = findings.is_empty();
    let report_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let github_payload = policy.to_github_rest_payload();
    let report_hash = hash_serializable(&(
        report_id,
        policy.policy_id,
        &policy.repository,
        &policy.branch,
        &missing_required_checks,
        &extra_required_checks,
        &findings,
        compliant,
        &github_payload,
        evaluated_at,
    ))?;
    Ok(BranchProtectionEvaluationReport {
        report_id,
        policy_id: policy.policy_id,
        repository: policy.repository.clone(),
        branch: policy.branch.clone(),
        missing_required_checks,
        extra_required_checks,
        findings,
        compliant,
        github_payload,
        report_hash,
        evaluated_at,
    })
}
