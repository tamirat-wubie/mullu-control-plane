use crate::{
    execute_chaos_rehearsal_plan, hash_serializable, ChaosExecutionMode, ChaosExecutionRun,
    ChaosExecutionRunStatus, ChaosRehearsalPlan, ChaosSeverity, EventId, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum StagingChaosRunMode {
    PlanOnly,
    #[default]
    GuardedDryRun,
    LiveStaging,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum StagingChaosRunStatus {
    Planned,
    Passed,
    Blocked,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct StagingChaosEnvironment {
    pub environment_name: String,
    pub cluster_id: String,
    pub namespace: String,
    #[serde(default)]
    pub allowed_targets: Vec<String>,
    #[serde(default)]
    pub destructive_allowed: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub approval_certificate_hash: Option<String>,
}

impl StagingChaosEnvironment {
    pub fn staging(namespace: impl Into<String>) -> Self {
        Self {
            environment_name: "staging".to_owned(),
            cluster_id: "local-staging".to_owned(),
            namespace: namespace.into(),
            allowed_targets: vec!["mind-api".to_owned(), "mind-worker".to_owned()],
            destructive_allowed: false,
            approval_certificate_hash: None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct StagingChaosSafetyPolicy {
    pub required_environment_prefix: String,
    #[serde(default)]
    pub allowed_namespaces: Vec<String>,
    pub require_approval_for_live: bool,
    pub allow_destructive_experiments: bool,
    pub require_zero_failed_dry_run: bool,
}

impl Default for StagingChaosSafetyPolicy {
    fn default() -> Self {
        Self {
            required_environment_prefix: "staging".to_owned(),
            allowed_namespaces: vec!["nested-mind-staging".to_owned(), "staging".to_owned()],
            require_approval_for_live: true,
            allow_destructive_experiments: false,
            require_zero_failed_dry_run: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct StagingChaosRunReport {
    pub staging_run_id: EventId,
    pub plan_id: EventId,
    pub environment: StagingChaosEnvironment,
    pub policy: StagingChaosSafetyPolicy,
    pub mode: StagingChaosRunMode,
    pub status: StagingChaosRunStatus,
    #[serde(default)]
    pub preflight_findings: Vec<String>,
    pub inner_run: ChaosExecutionRun,
    pub live_execution_permitted: bool,
    pub live_injection_executed: bool,
    pub report_hash: String,
    pub executed_at: OffsetDateTime,
}

impl StagingChaosRunReport {
    pub fn verify(&self, plan: &ChaosRehearsalPlan) -> MindResult<()> {
        if self.plan_id != plan.plan_id {
            return Err(MindError::Store(
                "staging chaos report references a different plan".to_owned(),
            ));
        }
        self.inner_run.verify(plan)?;
        let expected = hash_serializable(&(
            self.staging_run_id,
            self.plan_id,
            &self.environment,
            &self.policy,
            self.mode,
            self.status,
            &self.preflight_findings,
            &self.inner_run,
            self.live_execution_permitted,
            self.live_injection_executed,
            self.executed_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "staging chaos run report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn run_staging_chaos_rehearsal(
    plan: &ChaosRehearsalPlan,
    environment: StagingChaosEnvironment,
    mode: StagingChaosRunMode,
    policy: StagingChaosSafetyPolicy,
) -> MindResult<StagingChaosRunReport> {
    plan.verify()?;
    let preflight_findings = validate_staging_preflight(plan, &environment, mode, &policy);
    let preflight_failed = !preflight_findings.is_empty();
    let inner_mode = match mode {
        StagingChaosRunMode::PlanOnly => ChaosExecutionMode::PlanOnly,
        StagingChaosRunMode::GuardedDryRun | StagingChaosRunMode::LiveStaging => {
            ChaosExecutionMode::DeterministicDryRun
        }
    };
    let inner_run = execute_chaos_rehearsal_plan(plan, inner_mode)?;
    let live_execution_permitted = mode == StagingChaosRunMode::LiveStaging && !preflight_failed;
    let live_injection_executed = false;
    let status = if preflight_failed {
        StagingChaosRunStatus::Blocked
    } else if mode == StagingChaosRunMode::PlanOnly {
        StagingChaosRunStatus::Planned
    } else if inner_run.status == ChaosExecutionRunStatus::Failed {
        StagingChaosRunStatus::Failed
    } else {
        StagingChaosRunStatus::Passed
    };
    let staging_run_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        staging_run_id,
        plan.plan_id,
        &environment,
        &policy,
        mode,
        status,
        &preflight_findings,
        &inner_run,
        live_execution_permitted,
        live_injection_executed,
        executed_at,
    ))?;
    Ok(StagingChaosRunReport {
        staging_run_id,
        plan_id: plan.plan_id,
        environment,
        policy,
        mode,
        status,
        preflight_findings,
        inner_run,
        live_execution_permitted,
        live_injection_executed,
        report_hash,
        executed_at,
    })
}

fn validate_staging_preflight(
    plan: &ChaosRehearsalPlan,
    environment: &StagingChaosEnvironment,
    mode: StagingChaosRunMode,
    policy: &StagingChaosSafetyPolicy,
) -> Vec<String> {
    let mut findings = Vec::new();
    if !environment
        .environment_name
        .to_ascii_lowercase()
        .starts_with(&policy.required_environment_prefix.to_ascii_lowercase())
    {
        findings.push(format!(
            "environment `{}` does not start with required prefix `{}`",
            environment.environment_name, policy.required_environment_prefix
        ));
    }
    if !policy.allowed_namespaces.is_empty()
        && !policy
            .allowed_namespaces
            .iter()
            .any(|namespace| namespace == &environment.namespace)
    {
        findings.push(format!(
            "namespace `{}` is not allow-listed for staging chaos",
            environment.namespace
        ));
    }
    if mode == StagingChaosRunMode::LiveStaging
        && policy.require_approval_for_live
        && environment
            .approval_certificate_hash
            .as_deref()
            .unwrap_or_default()
            .is_empty()
    {
        findings.push("live staging chaos requires an approval certificate hash".to_owned());
    }
    let has_high_or_critical = plan.experiments.iter().any(|experiment| {
        matches!(
            experiment.severity,
            ChaosSeverity::High | ChaosSeverity::Critical
        )
    });
    if has_high_or_critical
        && !policy.allow_destructive_experiments
        && environment.destructive_allowed
    {
        findings.push(
            "destructive staging mode is enabled while policy disallows destructive experiments"
                .to_owned(),
        );
    }
    let allowed_targets = environment
        .allowed_targets
        .iter()
        .map(|target| target.to_ascii_lowercase())
        .collect::<BTreeSet<_>>();
    if allowed_targets.is_empty() {
        findings.push("staging chaos requires at least one allow-listed target".to_owned());
    }
    findings
}
