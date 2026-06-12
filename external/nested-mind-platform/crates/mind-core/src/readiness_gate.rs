use crate::{
    hash_serializable, ChaosRehearsalPlan, CreativeEngineeringReport, EventId,
    InvariantFuzzRunReport, MindResult,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ProductionReadinessStatus {
    Blocked,
    ReadyForStaging,
    ReadyForCanary,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReadinessBlocker {
    pub blocker_id: EventId,
    pub title: String,
    pub reason: String,
    pub required_action: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProductionReadinessGatePolicy {
    pub require_chaos_plan: bool,
    pub require_fuzz_rejections: bool,
    pub max_critical_fractures: usize,
    pub min_fuzz_cases: usize,
}

impl Default for ProductionReadinessGatePolicy {
    fn default() -> Self {
        Self {
            require_chaos_plan: true,
            require_fuzz_rejections: true,
            max_critical_fractures: 0,
            min_fuzz_cases: 12,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ProductionReadinessGateReport {
    pub gate_id: EventId,
    pub status: ProductionReadinessStatus,
    pub policy: ProductionReadinessGatePolicy,
    pub creative_report_id: EventId,
    pub chaos_plan_id: Option<EventId>,
    pub fuzz_run_id: Option<EventId>,
    #[serde(default)]
    pub blockers: Vec<ReadinessBlocker>,
    #[serde(default)]
    pub advisories: Vec<String>,
    pub gate_hash: String,
    pub evaluated_at: OffsetDateTime,
}

pub fn evaluate_production_readiness_gate(
    creative_report: &CreativeEngineeringReport,
    chaos_plan: Option<&ChaosRehearsalPlan>,
    fuzz_report: Option<&InvariantFuzzRunReport>,
    policy: ProductionReadinessGatePolicy,
) -> MindResult<ProductionReadinessGateReport> {
    let mut blockers = Vec::new();
    let mut advisories = Vec::new();

    let critical_fractures = creative_report
        .fracture_delta
        .iter()
        .filter(|fracture| fracture.to_ascii_lowercase().contains("critical"))
        .count();
    if critical_fractures > policy.max_critical_fractures {
        blockers.push(ReadinessBlocker {
            blocker_id: EventId::new(),
            title: "critical fracture budget exceeded".to_owned(),
            reason: format!(
                "{critical_fractures} critical fractures exceed allowed {}",
                policy.max_critical_fractures
            ),
            required_action: "resolve or explicitly waive critical fractures through governance"
                .to_owned(),
        });
    }

    if policy.require_chaos_plan {
        match chaos_plan {
            Some(plan) => plan.verify()?,
            None => blockers.push(ReadinessBlocker {
                blocker_id: EventId::new(),
                title: "missing chaos rehearsal plan".to_owned(),
                reason: "production promotion requires declared failure injections".to_owned(),
                required_action: "generate and execute a chaos rehearsal plan".to_owned(),
            }),
        }
    }

    if let Some(fuzz) = fuzz_report {
        if fuzz.cases.len() < policy.min_fuzz_cases {
            blockers.push(ReadinessBlocker {
                blocker_id: EventId::new(),
                title: "insufficient invariant fuzz coverage".to_owned(),
                reason: format!(
                    "{} cases < required {}",
                    fuzz.cases.len(),
                    policy.min_fuzz_cases
                ),
                required_action: "increase invariant fuzz case count".to_owned(),
            });
        }
        if policy.require_fuzz_rejections && fuzz.expected_reject_count == 0 {
            blockers.push(ReadinessBlocker {
                blocker_id: EventId::new(),
                title: "fuzz run has no destructive rejection cases".to_owned(),
                reason: "a readiness gate must prove fail-closed behavior".to_owned(),
                required_action: "include immutable, empty, wrong-target, or forbidden-key cases"
                    .to_owned(),
            });
        }
    } else {
        blockers.push(ReadinessBlocker {
            blocker_id: EventId::new(),
            title: "missing invariant fuzz report".to_owned(),
            reason: "production promotion requires deterministic invariant probes".to_owned(),
            required_action: "generate an invariant fuzz run report".to_owned(),
        });
    }

    if creative_report.high_leverage_first.is_empty() {
        advisories.push("creative report has no high-leverage suggestion ordering".to_owned());
    }
    if creative_report.input.deployment_stage != "production" {
        advisories.push(format!(
            "gate evaluated for `{}` stage; canary is the maximum non-production promotion target",
            creative_report.input.deployment_stage
        ));
    }

    let status = if !blockers.is_empty() {
        ProductionReadinessStatus::Blocked
    } else if creative_report.input.deployment_stage == "production" {
        ProductionReadinessStatus::ReadyForCanary
    } else {
        ProductionReadinessStatus::ReadyForStaging
    };
    let gate_id = EventId::new();
    let evaluated_at = OffsetDateTime::now_utc();
    let chaos_plan_id = chaos_plan.map(|plan| plan.plan_id);
    let fuzz_run_id = fuzz_report.map(|report| report.run_id);
    let gate_hash = hash_serializable(&(
        gate_id,
        status,
        &policy,
        creative_report.report_id,
        chaos_plan_id,
        fuzz_run_id,
        &blockers,
        &advisories,
        evaluated_at,
    ))?;
    Ok(ProductionReadinessGateReport {
        gate_id,
        status,
        policy,
        creative_report_id: creative_report.report_id,
        chaos_plan_id,
        fuzz_run_id,
        blockers,
        advisories,
        gate_hash,
        evaluated_at,
    })
}
