use crate::{
    hash_serializable, ChaosExecutionRun, ChaosExecutionRunStatus, EventId,
    InvariantFuzzExecutionReport, MindError, MindResult, ProductionReadinessGateReport,
    ProductionReadinessStatus, StagingChaosRunReport, StagingChaosRunStatus,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum CiCheckStatus {
    Passed,
    Failed,
    #[default]
    Skipped,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum CiGateStatus {
    Passed,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MandatoryCiGatePolicy {
    pub require_rust_format: bool,
    pub require_clippy: bool,
    pub require_unit_tests: bool,
    pub require_executable_readiness: bool,
    pub require_staging_chaos: bool,
    pub require_canary_readiness_without_waiver: bool,
    pub max_fuzz_failures: usize,
}

impl Default for MandatoryCiGatePolicy {
    fn default() -> Self {
        Self {
            require_rust_format: true,
            require_clippy: true,
            require_unit_tests: true,
            require_executable_readiness: true,
            require_staging_chaos: false,
            require_canary_readiness_without_waiver: false,
            max_fuzz_failures: 0,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct MandatoryCiGateInput {
    #[serde(default)]
    pub rust_format: CiCheckStatus,
    #[serde(default)]
    pub clippy: CiCheckStatus,
    #[serde(default)]
    pub unit_tests: CiCheckStatus,
    #[serde(default)]
    pub executable_readiness_tests: CiCheckStatus,
    #[serde(default)]
    pub readiness_gate: Option<ProductionReadinessGateReport>,
    #[serde(default)]
    pub chaos_execution: Option<ChaosExecutionRun>,
    #[serde(default)]
    pub invariant_fuzz_execution: Option<InvariantFuzzExecutionReport>,
    #[serde(default)]
    pub staging_chaos: Option<StagingChaosRunReport>,
    #[serde(default)]
    pub pull_request: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct MandatoryCiGateReport {
    pub ci_gate_id: EventId,
    pub status: CiGateStatus,
    pub policy: MandatoryCiGatePolicy,
    pub input: MandatoryCiGateInput,
    #[serde(default)]
    pub failed_checks: Vec<String>,
    #[serde(default)]
    pub advisories: Vec<String>,
    pub report_hash: String,
    pub evaluated_at: OffsetDateTime,
}

impl MandatoryCiGateReport {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.ci_gate_id,
            self.status,
            &self.policy,
            &self.input,
            &self.failed_checks,
            &self.advisories,
            self.evaluated_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "mandatory CI gate report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn evaluate_mandatory_ci_gate(
    input: MandatoryCiGateInput,
    policy: MandatoryCiGatePolicy,
) -> MindResult<MandatoryCiGateReport> {
    let mut failed_checks = Vec::new();
    let mut advisories = Vec::new();
    require_check(
        policy.require_rust_format,
        input.rust_format,
        "cargo fmt",
        &mut failed_checks,
    );
    require_check(
        policy.require_clippy,
        input.clippy,
        "cargo clippy",
        &mut failed_checks,
    );
    require_check(
        policy.require_unit_tests,
        input.unit_tests,
        "cargo test",
        &mut failed_checks,
    );
    require_check(
        policy.require_executable_readiness,
        input.executable_readiness_tests,
        "executable readiness tests",
        &mut failed_checks,
    );

    match &input.readiness_gate {
        Some(gate) => {
            if gate.status == ProductionReadinessStatus::Blocked {
                failed_checks.push("production readiness gate is blocked".to_owned());
            }
            if policy.require_canary_readiness_without_waiver
                && gate.status != ProductionReadinessStatus::ReadyForCanary
            {
                failed_checks
                    .push("canary readiness is required without waiver downgrade".to_owned());
            }
        }
        None => failed_checks.push("missing production readiness gate report".to_owned()),
    }

    match &input.chaos_execution {
        Some(run) if run.status == ChaosExecutionRunStatus::Failed => {
            failed_checks.push("chaos execution failed".to_owned());
        }
        Some(run) if run.status == ChaosExecutionRunStatus::Planned => {
            advisories.push("chaos execution is planned but not dry-run executed".to_owned());
        }
        Some(_) => {}
        None => advisories.push("no base chaos execution report attached".to_owned()),
    }

    match &input.invariant_fuzz_execution {
        Some(report) if report.failed_count > policy.max_fuzz_failures => {
            failed_checks.push(format!(
                "invariant fuzz failures {} exceed allowed {}",
                report.failed_count, policy.max_fuzz_failures
            ))
        }
        Some(_) => {}
        None => failed_checks.push("missing invariant fuzz execution report".to_owned()),
    }

    if policy.require_staging_chaos {
        match &input.staging_chaos {
            Some(report) if report.status == StagingChaosRunStatus::Passed => {}
            Some(report) => {
                failed_checks.push(format!("staging chaos status is {:?}", report.status))
            }
            None => failed_checks.push("missing staging chaos report".to_owned()),
        }
    }

    let status = if failed_checks.is_empty() {
        CiGateStatus::Passed
    } else {
        CiGateStatus::Failed
    };
    let ci_gate_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        ci_gate_id,
        status,
        &policy,
        &input,
        &failed_checks,
        &advisories,
        evaluated_at,
    ))?;
    Ok(MandatoryCiGateReport {
        ci_gate_id,
        status,
        policy,
        input,
        failed_checks,
        advisories,
        report_hash,
        evaluated_at,
    })
}

fn require_check(
    required: bool,
    status: CiCheckStatus,
    name: &str,
    failed_checks: &mut Vec<String>,
) {
    if required && status != CiCheckStatus::Passed {
        failed_checks.push(format!("{name} did not pass: {status:?}"));
    }
}
