use crate::{
    hash_serializable, EngineeringImplementationJob, EngineeringImplementationJobPlan, EventId,
    MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ImplementationEvidenceKind {
    PullRequest,
    TestRun,
    ReadinessGate,
    SecurityReview,
    RollbackPlan,
    MigrationPlan,
    Benchmark,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ImplementationEvidenceStatus {
    Satisfied,
    Incomplete,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImplementationEvidenceArtifact {
    pub artifact_id: EventId,
    pub kind: ImplementationEvidenceKind,
    pub title: String,
    pub uri: String,
    pub produced_by: String,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
    pub artifact_hash: String,
    pub created_at: OffsetDateTime,
}

impl ImplementationEvidenceArtifact {
    pub fn new(
        kind: ImplementationEvidenceKind,
        title: impl Into<String>,
        uri: impl Into<String>,
        produced_by: impl Into<String>,
        metadata: BTreeMap<String, String>,
    ) -> MindResult<Self> {
        let title = title.into();
        let uri = uri.into();
        let produced_by = produced_by.into();
        if title.trim().is_empty() || uri.trim().is_empty() || produced_by.trim().is_empty() {
            return Err(MindError::Store(
                "implementation evidence requires title, URI, and producer".to_owned(),
            ));
        }
        let artifact_id = EventId::new();
        let created_at = OffsetDateTime::now_utc();
        let artifact_hash = hash_serializable(&(
            artifact_id,
            kind,
            &title,
            &uri,
            &produced_by,
            &metadata,
            created_at,
        ))?;
        Ok(Self {
            artifact_id,
            kind,
            title,
            uri,
            produced_by,
            metadata,
            artifact_hash,
            created_at,
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.artifact_id,
            self.kind,
            &self.title,
            &self.uri,
            &self.produced_by,
            &self.metadata,
            self.created_at,
        ))?;
        if expected != self.artifact_hash {
            return Err(MindError::Store(
                "implementation evidence artifact hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImplementationJobEvidenceBundle {
    pub bundle_id: EventId,
    pub implementation_job_id: EventId,
    pub scheduled_job_id: EventId,
    #[serde(default)]
    pub required_kinds: BTreeSet<ImplementationEvidenceKind>,
    #[serde(default)]
    pub artifacts: Vec<ImplementationEvidenceArtifact>,
    #[serde(default)]
    pub missing_kinds: BTreeSet<ImplementationEvidenceKind>,
    pub status: ImplementationEvidenceStatus,
    pub bundle_hash: String,
    pub evaluated_at: OffsetDateTime,
}

impl ImplementationJobEvidenceBundle {
    pub fn verify(&self) -> MindResult<()> {
        for artifact in &self.artifacts {
            artifact.verify()?;
        }
        let expected = hash_serializable(&(
            self.bundle_id,
            self.implementation_job_id,
            self.scheduled_job_id,
            &self.required_kinds,
            &self.artifacts,
            &self.missing_kinds,
            self.status,
            self.evaluated_at,
        ))?;
        if expected != self.bundle_hash {
            return Err(MindError::Store(
                "implementation job evidence bundle hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImplementationEvidenceAutomationTarget {
    pub target_id: EventId,
    pub implementation_job_id: EventId,
    pub scheduled_job_id: EventId,
    pub branch_name: String,
    pub pull_request_title: String,
    #[serde(default)]
    pub test_commands: Vec<String>,
    #[serde(default)]
    pub required_evidence_kinds: BTreeSet<ImplementationEvidenceKind>,
    pub target_hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImplementationEvidenceAutomationPlan {
    pub automation_plan_id: EventId,
    pub implementation_plan_id: EventId,
    pub repository: String,
    pub base_branch: String,
    #[serde(default)]
    pub targets: Vec<ImplementationEvidenceAutomationTarget>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl ImplementationEvidenceAutomationPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.automation_plan_id,
            self.implementation_plan_id,
            &self.repository,
            &self.base_branch,
            &self.targets,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "implementation evidence automation plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn default_implementation_evidence_requirements() -> BTreeSet<ImplementationEvidenceKind> {
    BTreeSet::from([
        ImplementationEvidenceKind::PullRequest,
        ImplementationEvidenceKind::TestRun,
        ImplementationEvidenceKind::ReadinessGate,
        ImplementationEvidenceKind::RollbackPlan,
    ])
}

pub fn attach_implementation_evidence(
    job: &EngineeringImplementationJob,
    artifacts: Vec<ImplementationEvidenceArtifact>,
    required_kinds: BTreeSet<ImplementationEvidenceKind>,
) -> MindResult<ImplementationJobEvidenceBundle> {
    for artifact in &artifacts {
        artifact.verify()?;
    }
    let observed = artifacts
        .iter()
        .map(|artifact| artifact.kind)
        .collect::<BTreeSet<_>>();
    let missing_kinds = required_kinds
        .difference(&observed)
        .copied()
        .collect::<BTreeSet<_>>();
    let rejected = artifacts.iter().any(|artifact| {
        artifact
            .metadata
            .get("status")
            .is_some_and(|status| matches!(status.as_str(), "failed" | "rejected" | "blocked"))
    });
    let status = if rejected {
        ImplementationEvidenceStatus::Rejected
    } else if missing_kinds.is_empty() {
        ImplementationEvidenceStatus::Satisfied
    } else {
        ImplementationEvidenceStatus::Incomplete
    };
    let bundle_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let bundle_hash = hash_serializable(&(
        bundle_id,
        job.implementation_job_id,
        job.scheduled_job.job_id,
        &required_kinds,
        &artifacts,
        &missing_kinds,
        status,
        evaluated_at,
    ))?;
    Ok(ImplementationJobEvidenceBundle {
        bundle_id,
        implementation_job_id: job.implementation_job_id,
        scheduled_job_id: job.scheduled_job.job_id,
        required_kinds,
        artifacts,
        missing_kinds,
        status,
        bundle_hash,
        evaluated_at,
    })
}

pub fn plan_implementation_evidence_automation(
    plan: &EngineeringImplementationJobPlan,
    repository: impl Into<String>,
    base_branch: impl Into<String>,
) -> MindResult<ImplementationEvidenceAutomationPlan> {
    plan.verify()?;
    let repository = repository.into();
    let base_branch = base_branch.into();
    if repository.trim().is_empty() || base_branch.trim().is_empty() {
        return Err(MindError::Store(
            "implementation evidence automation requires repository and base branch".to_owned(),
        ));
    }
    let mut targets = Vec::new();
    for job in &plan.jobs {
        let target_id = EventId::new();
        let branch_name = format!(
            "engineering/{}-{}",
            sanitize_branch_component(&job.suggestion_title),
            job.implementation_job_id
        );
        let pull_request_title = format!("Implement: {}", job.suggestion_title);
        let test_commands = vec![
            "cargo fmt --all -- --check".to_owned(),
            "cargo clippy --workspace --all-targets -- -D warnings".to_owned(),
            "cargo test --workspace".to_owned(),
            "cargo test -p mind-core --test v18_executable_readiness_jobs".to_owned(),
        ];
        let required_evidence_kinds = default_implementation_evidence_requirements();
        let target_hash = hash_serializable(&(
            target_id,
            job.implementation_job_id,
            job.scheduled_job.job_id,
            &branch_name,
            &pull_request_title,
            &test_commands,
            &required_evidence_kinds,
        ))?;
        targets.push(ImplementationEvidenceAutomationTarget {
            target_id,
            implementation_job_id: job.implementation_job_id,
            scheduled_job_id: job.scheduled_job.job_id,
            branch_name,
            pull_request_title,
            test_commands,
            required_evidence_kinds,
            target_hash,
        });
    }
    let automation_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        automation_plan_id,
        plan.plan_id,
        &repository,
        &base_branch,
        &targets,
        created_at,
    ))?;
    Ok(ImplementationEvidenceAutomationPlan {
        automation_plan_id,
        implementation_plan_id: plan.plan_id,
        repository,
        base_branch,
        targets,
        plan_hash,
        created_at,
    })
}

pub fn synthetic_pull_request_evidence(
    target: &ImplementationEvidenceAutomationTarget,
    produced_by: impl Into<String>,
) -> MindResult<Vec<ImplementationEvidenceArtifact>> {
    let produced_by = produced_by.into();
    let mut pr_meta = BTreeMap::new();
    pr_meta.insert("branch".to_owned(), target.branch_name.clone());
    pr_meta.insert("status".to_owned(), "open".to_owned());
    let mut test_meta = BTreeMap::new();
    test_meta.insert(
        "commands".to_owned(),
        json!(&target.test_commands).to_string(),
    );
    test_meta.insert("status".to_owned(), "passed".to_owned());
    Ok(vec![
        ImplementationEvidenceArtifact::new(
            ImplementationEvidenceKind::PullRequest,
            target.pull_request_title.clone(),
            format!("pr://{}", target.target_id),
            produced_by.clone(),
            pr_meta,
        )?,
        ImplementationEvidenceArtifact::new(
            ImplementationEvidenceKind::TestRun,
            "mandatory readiness test run",
            format!("ci://{}", target.target_id),
            produced_by,
            test_meta,
        )?,
    ])
}

fn sanitize_branch_component(input: &str) -> String {
    let mut out = String::new();
    for ch in input.chars() {
        if ch.is_ascii_alphanumeric() {
            out.push(ch.to_ascii_lowercase());
        } else if !out.ends_with('-') {
            out.push('-');
        }
    }
    out.trim_matches('-').chars().take(48).collect::<String>()
}
