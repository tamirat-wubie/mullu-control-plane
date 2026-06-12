use crate::{hash_serializable, ChaosRehearsalPlan, ChaosSeverity, EventId, MindError, MindResult};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum ChaosExecutionMode {
    PlanOnly,
    #[default]
    DeterministicDryRun,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ChaosExperimentExecutionStatus {
    Planned,
    Passed,
    Failed,
    Skipped,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ChaosExecutionRunStatus {
    Planned,
    Passed,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChaosExperimentExecutionResult {
    pub result_id: EventId,
    pub experiment_id: EventId,
    pub experiment_name: String,
    pub severity: ChaosSeverity,
    pub status: ChaosExperimentExecutionStatus,
    pub containment_verified: bool,
    pub observed_signal: String,
    #[serde(default)]
    pub evidence: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub failure_reason: Option<String>,
    pub result_hash: String,
    pub executed_at: OffsetDateTime,
}

impl ChaosExperimentExecutionResult {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.result_id,
            self.experiment_id,
            &self.experiment_name,
            self.severity,
            self.status,
            self.containment_verified,
            &self.observed_signal,
            &self.evidence,
            &self.failure_reason,
            self.executed_at,
        ))?;
        if expected != self.result_hash {
            return Err(MindError::Store(
                "chaos experiment execution hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChaosExecutionRun {
    pub run_id: EventId,
    pub plan_id: EventId,
    pub mode: ChaosExecutionMode,
    pub status: ChaosExecutionRunStatus,
    #[serde(default)]
    pub results: Vec<ChaosExperimentExecutionResult>,
    pub passed_count: usize,
    pub failed_count: usize,
    pub skipped_count: usize,
    pub run_hash: String,
    pub executed_at: OffsetDateTime,
}

impl ChaosExecutionRun {
    pub fn verify(&self, plan: &ChaosRehearsalPlan) -> MindResult<()> {
        if self.plan_id != plan.plan_id {
            return Err(MindError::Store(
                "chaos execution run references a different plan".to_owned(),
            ));
        }
        for result in &self.results {
            result.verify()?;
        }
        let expected = hash_serializable(&(
            self.run_id,
            self.plan_id,
            self.mode,
            self.status,
            &self.results,
            self.passed_count,
            self.failed_count,
            self.skipped_count,
            self.executed_at,
        ))?;
        if expected != self.run_hash {
            return Err(MindError::Store(
                "chaos execution run hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn execute_chaos_rehearsal_plan(
    plan: &ChaosRehearsalPlan,
    mode: ChaosExecutionMode,
) -> MindResult<ChaosExecutionRun> {
    plan.verify()?;
    let mut results = Vec::new();
    for experiment in &plan.experiments {
        let executed_at = OffsetDateTime::now_utc();
        let (status, containment_verified, observed_signal, evidence, failure_reason) = match mode {
            ChaosExecutionMode::PlanOnly => (
                ChaosExperimentExecutionStatus::Planned,
                false,
                "experiment planned but not injected".to_owned(),
                experiment.evidence_required.clone(),
                None,
            ),
            ChaosExecutionMode::DeterministicDryRun => {
                let evidence = experiment
                    .evidence_required
                    .iter()
                    .map(|field| format!("dry_run_evidence:{field}"))
                    .collect::<Vec<_>>();
                (
                    ChaosExperimentExecutionStatus::Passed,
                    true,
                    experiment.expected_signal.clone(),
                    evidence,
                    None,
                )
            }
        };
        let result_id = EventId::new();
        let result_hash = hash_serializable(&(
            result_id,
            experiment.experiment_id,
            &experiment.name,
            experiment.severity,
            status,
            containment_verified,
            &observed_signal,
            &evidence,
            &failure_reason,
            executed_at,
        ))?;
        results.push(ChaosExperimentExecutionResult {
            result_id,
            experiment_id: experiment.experiment_id,
            experiment_name: experiment.name.clone(),
            severity: experiment.severity,
            status,
            containment_verified,
            observed_signal,
            evidence,
            failure_reason,
            result_hash,
            executed_at,
        });
    }
    let passed_count = results
        .iter()
        .filter(|result| result.status == ChaosExperimentExecutionStatus::Passed)
        .count();
    let failed_count = results
        .iter()
        .filter(|result| result.status == ChaosExperimentExecutionStatus::Failed)
        .count();
    let skipped_count = results
        .iter()
        .filter(|result| {
            matches!(
                result.status,
                ChaosExperimentExecutionStatus::Planned | ChaosExperimentExecutionStatus::Skipped
            )
        })
        .count();
    let status = if failed_count > 0 {
        ChaosExecutionRunStatus::Failed
    } else if skipped_count == results.len() {
        ChaosExecutionRunStatus::Planned
    } else {
        ChaosExecutionRunStatus::Passed
    };
    let run_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let run_hash = hash_serializable(&(
        run_id,
        plan.plan_id,
        mode,
        status,
        &results,
        passed_count,
        failed_count,
        skipped_count,
        executed_at,
    ))?;
    Ok(ChaosExecutionRun {
        run_id,
        plan_id: plan.plan_id,
        mode,
        status,
        results,
        passed_count,
        failed_count,
        skipped_count,
        run_hash,
        executed_at,
    })
}
