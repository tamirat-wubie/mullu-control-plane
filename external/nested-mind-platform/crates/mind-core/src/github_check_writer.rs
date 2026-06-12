use crate::{hash_serializable, EventId, GitHubCheckConclusion, MindError, MindResult};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum GitHubCheckRunWriteMode {
    #[default]
    PlanOnly,
    DryRun,
    WriteApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubCheckRunWriteStatus {
    Planned,
    DryRunAccepted,
    Written,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubCheckRunOutput {
    pub title: String,
    pub summary: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
}

impl GitHubCheckRunOutput {
    #[must_use]
    pub fn new(title: impl Into<String>, summary: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            summary: summary.into(),
            text: None,
        }
    }

    #[must_use]
    pub fn with_text(mut self, text: impl Into<String>) -> Self {
        self.text = Some(text.into());
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubCheckRunWriteRequest {
    pub request_id: EventId,
    pub repository: String,
    pub head_sha: String,
    pub name: String,
    pub status: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub conclusion: Option<GitHubCheckConclusion>,
    pub output: GitHubCheckRunOutput,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub external_id: Option<String>,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    pub request_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubCheckRunWriteRequest {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        repository: impl Into<String>,
        head_sha: impl Into<String>,
        name: impl Into<String>,
        status: impl Into<String>,
        conclusion: Option<GitHubCheckConclusion>,
        output: GitHubCheckRunOutput,
        details_url: Option<String>,
        external_id: Option<String>,
        labels: BTreeMap<String, String>,
    ) -> MindResult<Self> {
        let repository = repository.into();
        let head_sha = head_sha.into();
        let name = name.into();
        let status = status.into();
        if repository.trim().is_empty() || head_sha.trim().is_empty() || name.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub check-run write request requires repository, sha, and check name"
                    .to_owned(),
            ));
        }
        if output.title.trim().is_empty() || output.summary.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub check-run output requires title and summary".to_owned(),
            ));
        }
        let request_id = EventId::new();
        let created_at = OffsetDateTime::now_utc();
        let request_hash = hash_serializable(&(
            request_id,
            &repository,
            &head_sha,
            &name,
            &status,
            conclusion,
            &output,
            &details_url,
            &external_id,
            &labels,
            created_at,
        ))?;
        Ok(Self {
            request_id,
            repository,
            head_sha,
            name,
            status,
            conclusion,
            output,
            details_url,
            external_id,
            labels,
            request_hash,
            created_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.request_id,
            &self.repository,
            &self.head_sha,
            &self.name,
            &self.status,
            self.conclusion,
            &self.output,
            &self.details_url,
            &self.external_id,
            &self.labels,
            self.created_at,
        ))?;
        if expected != self.request_hash {
            return Err(MindError::Store(
                "GitHub check-run write request hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn github_payload(&self) -> Value {
        let mut payload = json!({
            "name": &self.name,
            "head_sha": &self.head_sha,
            "status": &self.status,
            "output": {
                "title": &self.output.title,
                "summary": &self.output.summary,
            }
        });
        if let Some(text) = &self.output.text {
            payload["output"]["text"] = json!(text);
        }
        if let Some(conclusion) = self.conclusion {
            payload["conclusion"] = json!(github_conclusion_to_api(conclusion));
        }
        if let Some(details_url) = &self.details_url {
            payload["details_url"] = json!(details_url);
        }
        if let Some(external_id) = &self.external_id {
            payload["external_id"] = json!(external_id);
        }
        payload
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct GitHubCheckRunWritePlan {
    pub plan_id: EventId,
    pub request: GitHubCheckRunWriteRequest,
    pub app_slug: String,
    pub mode: GitHubCheckRunWriteMode,
    pub required_permission: String,
    pub rest_endpoint: String,
    pub rest_payload: Value,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl GitHubCheckRunWritePlan {
    pub fn verify(&self) -> MindResult<()> {
        self.request.verify()?;
        let expected = hash_serializable(&(
            self.plan_id,
            &self.request,
            &self.app_slug,
            self.mode,
            &self.required_permission,
            &self.rest_endpoint,
            &self.rest_payload,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "GitHub check-run write plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubCheckRunWriteReceipt {
    pub receipt_id: EventId,
    pub plan_id: EventId,
    pub request_id: EventId,
    pub repository: String,
    pub head_sha: String,
    pub name: String,
    pub status: GitHubCheckRunWriteStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub github_check_run_id: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub html_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_hash: Option<String>,
    #[serde(default)]
    pub evidence: BTreeMap<String, String>,
    pub receipt_hash: String,
    pub written_at: OffsetDateTime,
}

impl GitHubCheckRunWriteReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.plan_id,
            self.request_id,
            &self.repository,
            &self.head_sha,
            &self.name,
            self.status,
            self.github_check_run_id,
            &self.html_url,
            &self.response_hash,
            &self.evidence,
            self.written_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "GitHub check-run write receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[allow(clippy::too_many_arguments)]
pub fn plan_github_check_run_write(
    repository: impl Into<String>,
    head_sha: impl Into<String>,
    name: impl Into<String>,
    output: GitHubCheckRunOutput,
    conclusion: Option<GitHubCheckConclusion>,
    details_url: Option<String>,
    external_id: Option<String>,
    app_slug: impl Into<String>,
    mode: GitHubCheckRunWriteMode,
) -> MindResult<GitHubCheckRunWritePlan> {
    let app_slug = app_slug.into();
    if app_slug.trim().is_empty() {
        return Err(MindError::Store(
            "GitHub check-run writer requires a GitHub App slug".to_owned(),
        ));
    }
    let status = if conclusion.is_some() {
        "completed"
    } else {
        "in_progress"
    };
    let request = GitHubCheckRunWriteRequest::new(
        repository,
        head_sha,
        name,
        status,
        conclusion,
        output,
        details_url,
        external_id,
        BTreeMap::from([("source".to_owned(), "nested-mind-readiness".to_owned())]),
    )?;
    let (owner, repo) = split_repository(&request.repository)?;
    let rest_endpoint = format!("/repos/{owner}/{repo}/check-runs");
    let rest_payload = request.github_payload();
    let plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let required_permission = "checks:write as GitHub App installation".to_owned();
    let plan_hash = hash_serializable(&(
        plan_id,
        &request,
        &app_slug,
        mode,
        &required_permission,
        &rest_endpoint,
        &rest_payload,
        created_at,
    ))?;
    Ok(GitHubCheckRunWritePlan {
        plan_id,
        request,
        app_slug,
        mode,
        required_permission,
        rest_endpoint,
        rest_payload,
        plan_hash,
        created_at,
    })
}

pub fn record_github_check_run_write_receipt(
    plan: &GitHubCheckRunWritePlan,
    github_check_run_id: Option<u64>,
    html_url: Option<String>,
    response_payload: Option<Value>,
) -> MindResult<GitHubCheckRunWriteReceipt> {
    plan.verify()?;
    let response_hash = response_payload
        .as_ref()
        .map(hash_serializable)
        .transpose()?;
    let mut evidence = BTreeMap::new();
    evidence.insert("endpoint".to_owned(), plan.rest_endpoint.clone());
    evidence.insert("mode".to_owned(), format!("{:?}", plan.mode));
    let status = match plan.mode {
        GitHubCheckRunWriteMode::PlanOnly => GitHubCheckRunWriteStatus::Planned,
        GitHubCheckRunWriteMode::DryRun => GitHubCheckRunWriteStatus::DryRunAccepted,
        GitHubCheckRunWriteMode::WriteApproved => {
            if github_check_run_id.is_some() {
                GitHubCheckRunWriteStatus::Written
            } else {
                GitHubCheckRunWriteStatus::Rejected
            }
        }
    };
    let receipt_id = EventId::new();
    let written_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.plan_id,
        plan.request.request_id,
        &plan.request.repository,
        &plan.request.head_sha,
        &plan.request.name,
        status,
        github_check_run_id,
        &html_url,
        &response_hash,
        &evidence,
        written_at,
    ))?;
    Ok(GitHubCheckRunWriteReceipt {
        receipt_id,
        plan_id: plan.plan_id,
        request_id: plan.request.request_id,
        repository: plan.request.repository.clone(),
        head_sha: plan.request.head_sha.clone(),
        name: plan.request.name.clone(),
        status,
        github_check_run_id,
        html_url,
        response_hash,
        evidence,
        receipt_hash,
        written_at,
    })
}

#[must_use]
pub fn github_conclusion_to_api(conclusion: GitHubCheckConclusion) -> &'static str {
    match conclusion {
        GitHubCheckConclusion::Success => "success",
        GitHubCheckConclusion::Neutral => "neutral",
        GitHubCheckConclusion::Skipped => "skipped",
        GitHubCheckConclusion::Failure => "failure",
        GitHubCheckConclusion::Cancelled => "cancelled",
        GitHubCheckConclusion::TimedOut => "timed_out",
        GitHubCheckConclusion::ActionRequired => "action_required",
        GitHubCheckConclusion::StartupFailure => "startup_failure",
        GitHubCheckConclusion::Stale | GitHubCheckConclusion::Unknown => "neutral",
    }
}

pub fn split_repository(repository: &str) -> MindResult<(&str, &str)> {
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
