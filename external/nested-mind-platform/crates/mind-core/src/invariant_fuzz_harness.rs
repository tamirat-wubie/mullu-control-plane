use crate::{
    hash_serializable, EvolutionEngine, FuzzMutationClass, Identity, InvariantFuzzCase,
    InvariantFuzzRunReport, LawRule, LawbookMigration, LawbookMigrationOp, Mind, MindError,
    MindProjection, MindResult, ProjectionPolicy,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct InvariantFuzzHarnessConfig {
    pub strict_forbid_password: bool,
    pub apply_successful_cases: bool,
    pub require_projection_redaction_for_secret_probes: bool,
}

impl Default for InvariantFuzzHarnessConfig {
    fn default() -> Self {
        Self {
            strict_forbid_password: true,
            apply_successful_cases: true,
            require_projection_redaction_for_secret_probes: true,
        }
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum InvariantFuzzCaseExecutionStatus {
    Passed,
    Failed,
    AcceptedUnexpectedly,
    RejectedUnexpectedly,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InvariantFuzzCaseExecution {
    pub case_id: crate::EventId,
    pub class: FuzzMutationClass,
    pub expected_acceptance: bool,
    pub actual_accepted: bool,
    pub status: InvariantFuzzCaseExecutionStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actual_error: Option<String>,
    pub oracle_passed: bool,
    pub before_history_len: usize,
    pub after_history_len: usize,
    pub public_projection_leak_detected: bool,
    pub execution_hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InvariantFuzzExecutionReport {
    pub execution_id: crate::EventId,
    pub run_id: crate::EventId,
    pub target_mind_id: crate::MindId,
    pub config: InvariantFuzzHarnessConfig,
    #[serde(default)]
    pub case_results: Vec<InvariantFuzzCaseExecution>,
    pub passed_count: usize,
    pub failed_count: usize,
    pub accepted_unexpectedly_count: usize,
    pub rejected_unexpectedly_count: usize,
    pub execution_hash: String,
    pub executed_at: OffsetDateTime,
}

impl InvariantFuzzExecutionReport {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.execution_id,
            self.run_id,
            self.target_mind_id,
            &self.config,
            &self.case_results,
            self.passed_count,
            self.failed_count,
            self.accepted_unexpectedly_count,
            self.rejected_unexpectedly_count,
            self.executed_at,
        ))?;
        if expected != self.execution_hash {
            return Err(MindError::Store(
                "invariant fuzz execution hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn execute_invariant_fuzz_run(
    run: &InvariantFuzzRunReport,
    config: InvariantFuzzHarnessConfig,
) -> MindResult<InvariantFuzzExecutionReport> {
    let baseline = strict_baseline_mind(run, &config)?;
    let mut case_results = Vec::new();
    for case in &run.cases {
        case_results.push(execute_case(&baseline, case, &config)?);
    }
    let passed_count = case_results
        .iter()
        .filter(|result| result.status == InvariantFuzzCaseExecutionStatus::Passed)
        .count();
    let accepted_unexpectedly_count = case_results
        .iter()
        .filter(|result| result.status == InvariantFuzzCaseExecutionStatus::AcceptedUnexpectedly)
        .count();
    let rejected_unexpectedly_count = case_results
        .iter()
        .filter(|result| result.status == InvariantFuzzCaseExecutionStatus::RejectedUnexpectedly)
        .count();
    let failed_count = case_results.len().saturating_sub(passed_count);
    let execution_id = crate::EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let execution_hash = hash_serializable(&(
        execution_id,
        run.run_id,
        run.target_mind_id,
        &config,
        &case_results,
        passed_count,
        failed_count,
        accepted_unexpectedly_count,
        rejected_unexpectedly_count,
        executed_at,
    ))?;
    Ok(InvariantFuzzExecutionReport {
        execution_id,
        run_id: run.run_id,
        target_mind_id: run.target_mind_id,
        config,
        case_results,
        passed_count,
        failed_count,
        accepted_unexpectedly_count,
        rejected_unexpectedly_count,
        execution_hash,
        executed_at,
    })
}

fn strict_baseline_mind(
    run: &InvariantFuzzRunReport,
    config: &InvariantFuzzHarnessConfig,
) -> MindResult<Mind> {
    let mut mind = Mind::from_identity(Identity::root_with_id(run.target_mind_id, "fuzz-target"));
    if config.strict_forbid_password {
        let migration = LawbookMigration::new(
            mind.lawbook().version(),
            mind.lawbook().version() + 1,
            "invariant-fuzz-harness",
            "forbid password cells during strict invariant fuzz execution",
            vec![LawbookMigrationOp::AddRule {
                rule: LawRule::ForbidKey {
                    key: "password".to_owned(),
                },
            }],
        );
        let plan = EvolutionEngine::evaluate_lawbook_migration(&mind, migration)?;
        let _ = EvolutionEngine::apply_plan(&mut mind, plan)?;
    }
    Ok(mind)
}

fn execute_case(
    baseline: &Mind,
    case: &InvariantFuzzCase,
    config: &InvariantFuzzHarnessConfig,
) -> MindResult<InvariantFuzzCaseExecution> {
    let mut mind = baseline.clone();
    let before_history_len = mind.history().len();
    let mut actual_error = None;
    let mut public_projection_leak_detected = false;
    let actual_accepted = match EvolutionEngine::evaluate(&mind, case.proposal.clone()) {
        Ok(plan) => {
            if config.apply_successful_cases {
                let _ = EvolutionEngine::apply_plan(&mut mind, plan)?;
            }
            public_projection_leak_detected = public_projection_has_sensitive_keys(&mind);
            true
        }
        Err(error) => {
            actual_error = Some(error.to_string());
            false
        }
    };
    let after_history_len = mind.history().len();
    let oracle_passed = oracle_passed(
        case,
        actual_accepted,
        actual_error.as_deref(),
        public_projection_leak_detected,
        config,
    );
    let status = if oracle_passed {
        InvariantFuzzCaseExecutionStatus::Passed
    } else if actual_accepted && !case.expected_acceptance {
        InvariantFuzzCaseExecutionStatus::AcceptedUnexpectedly
    } else if !actual_accepted && case.expected_acceptance {
        InvariantFuzzCaseExecutionStatus::RejectedUnexpectedly
    } else {
        InvariantFuzzCaseExecutionStatus::Failed
    };
    let execution_hash = hash_serializable(&(
        case.case_id,
        case.class,
        case.expected_acceptance,
        actual_accepted,
        status,
        &actual_error,
        oracle_passed,
        before_history_len,
        after_history_len,
        public_projection_leak_detected,
    ))?;
    Ok(InvariantFuzzCaseExecution {
        case_id: case.case_id,
        class: case.class,
        expected_acceptance: case.expected_acceptance,
        actual_accepted,
        status,
        actual_error,
        oracle_passed,
        before_history_len,
        after_history_len,
        public_projection_leak_detected,
        execution_hash,
    })
}

fn oracle_passed(
    case: &InvariantFuzzCase,
    actual_accepted: bool,
    actual_error: Option<&str>,
    public_projection_leak_detected: bool,
    config: &InvariantFuzzHarnessConfig,
) -> bool {
    if case.class == FuzzMutationClass::ProjectionSecretLeakProbe {
        return actual_accepted
            && (!config.require_projection_redaction_for_secret_probes
                || !public_projection_leak_detected);
    }
    if case.expected_acceptance {
        return actual_accepted;
    }
    if actual_accepted {
        return false;
    }
    match (&case.expected_rejection_contains, actual_error) {
        (Some(expected), Some(actual)) => actual
            .to_ascii_lowercase()
            .contains(&expected.to_ascii_lowercase()),
        (None, _) => true,
        _ => false,
    }
}

fn public_projection_has_sensitive_keys(mind: &Mind) -> bool {
    let projection = MindProjection::with_policy(mind, &ProjectionPolicy::public_default());
    projection.state.cells().keys().any(|key| {
        let lowered = key.to_ascii_lowercase();
        lowered.starts_with("secret.")
            || lowered.starts_with("private.")
            || lowered.starts_with("auth.")
            || lowered.contains("password")
            || lowered.contains("token")
            || lowered.contains("credential")
    })
}
