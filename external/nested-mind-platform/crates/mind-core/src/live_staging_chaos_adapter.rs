use crate::{
    hash_serializable, ChaosRehearsalPlan, EventId, MindError, MindResult, StagingChaosRunReport,
    StagingChaosRunStatus,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum LiveChaosAdapterBackend {
    KubernetesServerDryRun,
    ArgoRolloutAnalysis,
    HttpGateway,
    ManualRunbook,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum LiveChaosAdapterMode {
    PlanOnly,
    #[default]
    ServerDryRun,
    LiveApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum LiveChaosAdapterStatus {
    Planned,
    DryRunAccepted,
    LiveAccepted,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveStagingChaosAdapterPlan {
    pub adapter_plan_id: EventId,
    pub rehearsal_plan_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub staging_run_id: Option<EventId>,
    pub backend: LiveChaosAdapterBackend,
    pub mode: LiveChaosAdapterMode,
    pub namespace: String,
    #[serde(default)]
    pub allowed_targets: Vec<String>,
    #[serde(default)]
    pub commands: Vec<String>,
    #[serde(default)]
    pub safety_labels: BTreeMap<String, String>,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl LiveStagingChaosAdapterPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.adapter_plan_id,
            self.rehearsal_plan_id,
            self.staging_run_id,
            self.backend,
            self.mode,
            &self.namespace,
            &self.allowed_targets,
            &self.commands,
            &self.safety_labels,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "live staging chaos adapter plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LiveStagingChaosAdapterReceipt {
    pub receipt_id: EventId,
    pub adapter_plan_id: EventId,
    pub backend: LiveChaosAdapterBackend,
    pub mode: LiveChaosAdapterMode,
    pub status: LiveChaosAdapterStatus,
    #[serde(default)]
    pub observed_signals: Vec<String>,
    #[serde(default)]
    pub evidence: BTreeMap<String, String>,
    pub receipt_hash: String,
    pub executed_at: OffsetDateTime,
}

impl LiveStagingChaosAdapterReceipt {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.receipt_id,
            self.adapter_plan_id,
            self.backend,
            self.mode,
            self.status,
            &self.observed_signals,
            &self.evidence,
            self.executed_at,
        ))?;
        if expected != self.receipt_hash {
            return Err(MindError::Store(
                "live staging chaos adapter receipt hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_live_staging_chaos_adapter(
    rehearsal: &ChaosRehearsalPlan,
    staging_report: Option<&StagingChaosRunReport>,
    backend: LiveChaosAdapterBackend,
    mode: LiveChaosAdapterMode,
) -> MindResult<LiveStagingChaosAdapterPlan> {
    rehearsal.verify()?;
    let namespace = staging_report
        .map(|report| report.environment.namespace.clone())
        .unwrap_or_else(|| "nested-mind-staging".to_owned());
    let allowed_targets = staging_report
        .map(|report| report.environment.allowed_targets.clone())
        .unwrap_or_else(|| vec!["mind-api".to_owned(), "mind-worker".to_owned()]);
    let staging_run_id = staging_report.map(|report| report.staging_run_id);
    let commands = rehearsal
        .experiments
        .iter()
        .map(|experiment| match backend {
            LiveChaosAdapterBackend::KubernetesServerDryRun => format!(
                "kubectl -n {namespace} annotate deployment/{target} chaos.mullusi.com/experiment={} --dry-run=server",
                experiment.experiment_id,
                target = allowed_targets.first().cloned().unwrap_or_else(|| "mind-api".to_owned())
            ),
            LiveChaosAdapterBackend::ArgoRolloutAnalysis => format!(
                "argo rollouts analysisrun create {} --dry-run",
                experiment.experiment_id
            ),
            LiveChaosAdapterBackend::HttpGateway => format!(
                "POST /chaos/experiments/{} mode={mode:?}",
                experiment.experiment_id
            ),
            LiveChaosAdapterBackend::ManualRunbook => format!(
                "manual runbook step for experiment {}",
                experiment.experiment_id
            ),
        })
        .collect::<Vec<_>>();
    let safety_labels = BTreeMap::from([
        ("environment".to_owned(), namespace.clone()),
        (
            "live_side_effects".to_owned(),
            matches!(mode, LiveChaosAdapterMode::LiveApproved).to_string(),
        ),
        ("requires_receipt".to_owned(), "true".to_owned()),
    ]);
    let adapter_plan_id = EventId::new();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        adapter_plan_id,
        rehearsal.plan_id,
        staging_run_id,
        backend,
        mode,
        &namespace,
        &allowed_targets,
        &commands,
        &safety_labels,
        created_at,
    ))?;
    Ok(LiveStagingChaosAdapterPlan {
        adapter_plan_id,
        rehearsal_plan_id: rehearsal.plan_id,
        staging_run_id,
        backend,
        mode,
        namespace,
        allowed_targets,
        commands,
        safety_labels,
        plan_hash,
        created_at,
    })
}

pub fn execute_live_staging_chaos_adapter_dry_run(
    plan: &LiveStagingChaosAdapterPlan,
) -> MindResult<LiveStagingChaosAdapterReceipt> {
    plan.verify()?;
    let mut evidence = BTreeMap::new();
    evidence.insert("command_count".to_owned(), plan.commands.len().to_string());
    evidence.insert("namespace".to_owned(), plan.namespace.clone());
    let status = match plan.mode {
        LiveChaosAdapterMode::PlanOnly => LiveChaosAdapterStatus::Planned,
        LiveChaosAdapterMode::ServerDryRun => LiveChaosAdapterStatus::DryRunAccepted,
        LiveChaosAdapterMode::LiveApproved => {
            if plan
                .safety_labels
                .get("live_side_effects")
                .is_some_and(|value| value == "true")
            {
                LiveChaosAdapterStatus::LiveAccepted
            } else {
                LiveChaosAdapterStatus::Rejected
            }
        }
    };
    let observed_signals = if status == LiveChaosAdapterStatus::Rejected {
        vec!["adapter rejected live mode without safety label".to_owned()]
    } else {
        vec!["adapter plan validated without mutation".to_owned()]
    };
    let receipt_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let receipt_hash = hash_serializable(&(
        receipt_id,
        plan.adapter_plan_id,
        plan.backend,
        plan.mode,
        status,
        &observed_signals,
        &evidence,
        executed_at,
    ))?;
    Ok(LiveStagingChaosAdapterReceipt {
        receipt_id,
        adapter_plan_id: plan.adapter_plan_id,
        backend: plan.backend,
        mode: plan.mode,
        status,
        observed_signals,
        evidence,
        receipt_hash,
        executed_at,
    })
}

pub fn require_staging_report_passed(
    report: &StagingChaosRunReport,
    plan: &ChaosRehearsalPlan,
) -> MindResult<()> {
    report.verify(plan)?;
    if report.status != StagingChaosRunStatus::Passed {
        return Err(MindError::Store(
            "staging chaos report must pass before live adapter planning".to_owned(),
        ));
    }
    Ok(())
}
