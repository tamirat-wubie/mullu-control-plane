use crate::{
    hash_serializable, EventId, ImplementationEvidenceArtifact, ImplementationEvidenceKind,
    MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum GitHubEvidenceSource {
    #[default]
    RestApi,
    Webhook,
    Fixture,
    Manual,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubCheckConclusion {
    Success,
    Neutral,
    Skipped,
    Failure,
    Cancelled,
    TimedOut,
    ActionRequired,
    StartupFailure,
    Stale,
    Unknown,
}

impl GitHubCheckConclusion {
    #[must_use]
    pub fn from_github(value: Option<&str>) -> Self {
        match value.unwrap_or_default() {
            "success" => Self::Success,
            "neutral" => Self::Neutral,
            "skipped" => Self::Skipped,
            "failure" => Self::Failure,
            "cancelled" => Self::Cancelled,
            "timed_out" => Self::TimedOut,
            "action_required" => Self::ActionRequired,
            "startup_failure" => Self::StartupFailure,
            "stale" => Self::Stale,
            _ => Self::Unknown,
        }
    }

    #[must_use]
    pub fn satisfies_required_check(self) -> bool {
        matches!(self, Self::Success | Self::Neutral | Self::Skipped)
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum GitHubEvidenceBundleStatus {
    Satisfied,
    Incomplete,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubPullRequestEvidence {
    pub evidence_id: EventId,
    pub repository: String,
    pub pull_request_number: u64,
    pub title: String,
    pub author: String,
    pub base_branch: String,
    pub head_branch: String,
    pub head_sha: String,
    pub draft: bool,
    pub merged: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub review_decision: Option<String>,
    #[serde(default)]
    pub labels: Vec<String>,
    pub source: GitHubEvidenceSource,
    pub evidence_hash: String,
    pub observed_at: OffsetDateTime,
}

impl GitHubPullRequestEvidence {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        repository: impl Into<String>,
        pull_request_number: u64,
        title: impl Into<String>,
        author: impl Into<String>,
        base_branch: impl Into<String>,
        head_branch: impl Into<String>,
        head_sha: impl Into<String>,
        draft: bool,
        merged: bool,
        review_decision: Option<String>,
        labels: Vec<String>,
        source: GitHubEvidenceSource,
    ) -> MindResult<Self> {
        let repository = repository.into();
        let title = title.into();
        let author = author.into();
        let base_branch = base_branch.into();
        let head_branch = head_branch.into();
        let head_sha = head_sha.into();
        if repository.trim().is_empty()
            || head_sha.trim().is_empty()
            || base_branch.trim().is_empty()
        {
            return Err(MindError::Store(
                "GitHub PR evidence requires repository, base branch, and head sha".to_owned(),
            ));
        }
        let evidence_id = EventId::new();
        let observed_at = OffsetDateTime::now_utc();
        let evidence_hash = hash_serializable(&(
            evidence_id,
            &repository,
            pull_request_number,
            &title,
            &author,
            &base_branch,
            &head_branch,
            &head_sha,
            draft,
            merged,
            &review_decision,
            &labels,
            source,
            observed_at,
        ))?;
        Ok(Self {
            evidence_id,
            repository,
            pull_request_number,
            title,
            author,
            base_branch,
            head_branch,
            head_sha,
            draft,
            merged,
            review_decision,
            labels,
            source,
            evidence_hash,
            observed_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.evidence_id,
            &self.repository,
            self.pull_request_number,
            &self.title,
            &self.author,
            &self.base_branch,
            &self.head_branch,
            &self.head_sha,
            self.draft,
            self.merged,
            &self.review_decision,
            &self.labels,
            self.source,
            self.observed_at,
        ))?;
        if expected != self.evidence_hash {
            return Err(MindError::Store(
                "GitHub PR evidence hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubCheckRunEvidence {
    pub evidence_id: EventId,
    pub repository: String,
    pub head_sha: String,
    pub name: String,
    pub status: String,
    pub conclusion: GitHubCheckConclusion,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub app_slug: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details_url: Option<String>,
    pub source: GitHubEvidenceSource,
    pub evidence_hash: String,
    pub observed_at: OffsetDateTime,
}

impl GitHubCheckRunEvidence {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        repository: impl Into<String>,
        head_sha: impl Into<String>,
        name: impl Into<String>,
        status: impl Into<String>,
        conclusion: GitHubCheckConclusion,
        app_slug: Option<String>,
        details_url: Option<String>,
        source: GitHubEvidenceSource,
    ) -> MindResult<Self> {
        let repository = repository.into();
        let head_sha = head_sha.into();
        let name = name.into();
        let status = status.into();
        if repository.trim().is_empty() || head_sha.trim().is_empty() || name.trim().is_empty() {
            return Err(MindError::Store(
                "GitHub check evidence requires repository, sha, and check name".to_owned(),
            ));
        }
        let evidence_id = EventId::new();
        let observed_at = OffsetDateTime::now_utc();
        let evidence_hash = hash_serializable(&(
            evidence_id,
            &repository,
            &head_sha,
            &name,
            &status,
            conclusion,
            &app_slug,
            &details_url,
            source,
            observed_at,
        ))?;
        Ok(Self {
            evidence_id,
            repository,
            head_sha,
            name,
            status,
            conclusion,
            app_slug,
            details_url,
            source,
            evidence_hash,
            observed_at,
        })
    }

    #[must_use]
    pub fn satisfies_required_check(&self) -> bool {
        self.status == "completed" && self.conclusion.satisfies_required_check()
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.evidence_id,
            &self.repository,
            &self.head_sha,
            &self.name,
            &self.status,
            self.conclusion,
            &self.app_slug,
            &self.details_url,
            self.source,
            self.observed_at,
        ))?;
        if expected != self.evidence_hash {
            return Err(MindError::Store(
                "GitHub check evidence hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct GitHubReadinessEvidenceBundle {
    pub bundle_id: EventId,
    pub repository: String,
    pub pull_request: GitHubPullRequestEvidence,
    #[serde(default)]
    pub check_runs: Vec<GitHubCheckRunEvidence>,
    #[serde(default)]
    pub required_check_names: BTreeSet<String>,
    #[serde(default)]
    pub missing_required_checks: BTreeSet<String>,
    #[serde(default)]
    pub failing_required_checks: BTreeMap<String, GitHubCheckConclusion>,
    pub status: GitHubEvidenceBundleStatus,
    pub bundle_hash: String,
    pub collected_at: OffsetDateTime,
}

impl GitHubReadinessEvidenceBundle {
    pub fn verify(&self) -> MindResult<()> {
        self.pull_request.verify()?;
        for check in &self.check_runs {
            check.verify()?;
        }
        let expected = hash_serializable(&(
            self.bundle_id,
            &self.repository,
            &self.pull_request,
            &self.check_runs,
            &self.required_check_names,
            &self.missing_required_checks,
            &self.failing_required_checks,
            self.status,
            self.collected_at,
        ))?;
        if expected != self.bundle_hash {
            return Err(MindError::Store(
                "GitHub readiness evidence bundle hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }

    pub fn to_implementation_artifacts(
        &self,
        produced_by: impl Into<String>,
    ) -> MindResult<Vec<ImplementationEvidenceArtifact>> {
        self.verify()?;
        let produced_by = produced_by.into();
        let status = match self.status {
            GitHubEvidenceBundleStatus::Satisfied => "passed",
            GitHubEvidenceBundleStatus::Incomplete => "blocked",
            GitHubEvidenceBundleStatus::Rejected => "failed",
        };
        let pr_uri = format!(
            "github://{}/pull/{}",
            self.repository, self.pull_request.pull_request_number
        );
        let checks_uri = format!(
            "github://{}/commit/{}/checks",
            self.repository, self.pull_request.head_sha
        );
        Ok(vec![
            ImplementationEvidenceArtifact::new(
                ImplementationEvidenceKind::PullRequest,
                format!(
                    "PR #{} {}",
                    self.pull_request.pull_request_number, self.pull_request.title
                ),
                pr_uri,
                produced_by.clone(),
                BTreeMap::from([
                    ("status".to_owned(), status.to_owned()),
                    ("bundle_hash".to_owned(), self.bundle_hash.clone()),
                ]),
            )?,
            ImplementationEvidenceArtifact::new(
                ImplementationEvidenceKind::TestRun,
                "GitHub required checks evidence",
                checks_uri,
                produced_by,
                BTreeMap::from([
                    ("status".to_owned(), status.to_owned()),
                    (
                        "missing_required_checks".to_owned(),
                        self.missing_required_checks.len().to_string(),
                    ),
                    (
                        "failing_required_checks".to_owned(),
                        self.failing_required_checks.len().to_string(),
                    ),
                ]),
            )?,
        ])
    }
}

pub fn collect_github_readiness_evidence(
    pull_request: GitHubPullRequestEvidence,
    check_runs: Vec<GitHubCheckRunEvidence>,
    required_check_names: BTreeSet<String>,
) -> MindResult<GitHubReadinessEvidenceBundle> {
    pull_request.verify()?;
    if pull_request.draft {
        // Draft PRs are useful evidence but cannot satisfy promotion readiness.
    }
    for check in &check_runs {
        check.verify()?;
        if check.repository != pull_request.repository || check.head_sha != pull_request.head_sha {
            return Err(MindError::Store(
                "GitHub check evidence does not match PR repository/head sha".to_owned(),
            ));
        }
    }
    let observed = check_runs
        .iter()
        .map(|check| check.name.clone())
        .collect::<BTreeSet<_>>();
    let missing_required_checks = required_check_names
        .difference(&observed)
        .cloned()
        .collect::<BTreeSet<_>>();
    let mut failing_required_checks = BTreeMap::new();
    for required in &required_check_names {
        if let Some(check) = check_runs.iter().find(|check| &check.name == required) {
            if !check.satisfies_required_check() {
                failing_required_checks.insert(required.clone(), check.conclusion);
            }
        }
    }
    let status = if pull_request.draft || !missing_required_checks.is_empty() {
        GitHubEvidenceBundleStatus::Incomplete
    } else if !failing_required_checks.is_empty() {
        GitHubEvidenceBundleStatus::Rejected
    } else {
        GitHubEvidenceBundleStatus::Satisfied
    };
    let repository = pull_request.repository.clone();
    let bundle_id = EventId::new();
    let collected_at = OffsetDateTime::now_utc();
    let bundle_hash = hash_serializable(&(
        bundle_id,
        &repository,
        &pull_request,
        &check_runs,
        &required_check_names,
        &missing_required_checks,
        &failing_required_checks,
        status,
        collected_at,
    ))?;
    Ok(GitHubReadinessEvidenceBundle {
        bundle_id,
        repository,
        pull_request,
        check_runs,
        required_check_names,
        missing_required_checks,
        failing_required_checks,
        status,
        bundle_hash,
        collected_at,
    })
}

pub fn required_readiness_check_names() -> BTreeSet<String> {
    BTreeSet::from([
        "cargo fmt".to_owned(),
        "cargo clippy".to_owned(),
        "cargo test".to_owned(),
        "mandatory-readiness-gates".to_owned(),
        "readiness-evidence".to_owned(),
    ])
}
