use crate::{
    hash_serializable, BranchProtectionReconcilePlan, BranchProtectionReconcileReceipt,
    BranchProtectionReconcileStatus, EventId, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum BranchProtectionWorkerMode {
    #[default]
    PlanOnly,
    DryRun,
    ApplyApproved,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum BranchProtectionWorkerStatus {
    Planned,
    NoDrift,
    Applied,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BranchProtectionWorkerPlan {
    pub worker_plan_id: EventId,
    #[serde(default)]
    pub reconcile_plan_ids: Vec<EventId>,
    pub repository: String,
    pub branch: String,
    pub mode: BranchProtectionWorkerMode,
    pub plan_hash: String,
    pub created_at: OffsetDateTime,
}

impl BranchProtectionWorkerPlan {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.worker_plan_id,
            &self.reconcile_plan_ids,
            &self.repository,
            &self.branch,
            self.mode,
            self.created_at,
        ))?;
        if expected != self.plan_hash {
            return Err(MindError::Store(
                "branch-protection worker plan hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BranchProtectionWorkerReport {
    pub report_id: EventId,
    pub worker_plan_id: EventId,
    pub repository: String,
    pub branch: String,
    pub status: BranchProtectionWorkerStatus,
    #[serde(default)]
    pub reconcile_receipt_ids: Vec<EventId>,
    #[serde(default)]
    pub rejected_reasons: Vec<String>,
    pub report_hash: String,
    pub executed_at: OffsetDateTime,
}

impl BranchProtectionWorkerReport {
    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&(
            self.report_id,
            self.worker_plan_id,
            &self.repository,
            &self.branch,
            self.status,
            &self.reconcile_receipt_ids,
            &self.rejected_reasons,
            self.executed_at,
        ))?;
        if expected != self.report_hash {
            return Err(MindError::Store(
                "branch-protection worker report hash mismatch".to_owned(),
            ));
        }
        Ok(())
    }
}

pub fn plan_branch_protection_reconcile_worker(
    plans: &[BranchProtectionReconcilePlan],
    mode: BranchProtectionWorkerMode,
) -> MindResult<BranchProtectionWorkerPlan> {
    if plans.is_empty() {
        return Err(MindError::Store(
            "branch-protection worker requires at least one reconcile plan".to_owned(),
        ));
    }
    let repository = plans[0].policy.repository.clone();
    let branch = plans[0].policy.branch.clone();
    for plan in plans {
        plan.verify()?;
        if plan.policy.repository != repository || plan.policy.branch != branch {
            return Err(MindError::Store(
                "branch-protection worker plans must target one repository branch".to_owned(),
            ));
        }
    }
    let worker_plan_id = EventId::new();
    let reconcile_plan_ids = plans
        .iter()
        .map(|plan| plan.reconcile_id)
        .collect::<Vec<_>>();
    let created_at = OffsetDateTime::now_utc();
    let plan_hash = hash_serializable(&(
        worker_plan_id,
        &reconcile_plan_ids,
        &repository,
        &branch,
        mode,
        created_at,
    ))?;
    Ok(BranchProtectionWorkerPlan {
        worker_plan_id,
        reconcile_plan_ids,
        repository,
        branch,
        mode,
        plan_hash,
        created_at,
    })
}

pub fn record_branch_protection_worker_report(
    plan: &BranchProtectionWorkerPlan,
    receipts: &[BranchProtectionReconcileReceipt],
) -> MindResult<BranchProtectionWorkerReport> {
    plan.verify()?;
    let mut rejected_reasons = Vec::new();
    let mut receipt_ids = Vec::new();
    let mut applied = false;
    for receipt in receipts {
        receipt.verify()?;
        receipt_ids.push(receipt.receipt_id);
        match receipt.status {
            BranchProtectionReconcileStatus::Applied => applied = true,
            BranchProtectionReconcileStatus::Rejected => {
                rejected_reasons.push(format!("reconcile receipt {} rejected", receipt.receipt_id))
            }
            _ => {}
        }
    }
    let status = if !rejected_reasons.is_empty() {
        BranchProtectionWorkerStatus::Rejected
    } else if applied {
        BranchProtectionWorkerStatus::Applied
    } else if receipts.is_empty() || plan.mode == BranchProtectionWorkerMode::PlanOnly {
        BranchProtectionWorkerStatus::Planned
    } else {
        BranchProtectionWorkerStatus::NoDrift
    };
    let report_id = EventId::new();
    let executed_at = OffsetDateTime::now_utc();
    let report_hash = hash_serializable(&(
        report_id,
        plan.worker_plan_id,
        &plan.repository,
        &plan.branch,
        status,
        &receipt_ids,
        &rejected_reasons,
        executed_at,
    ))?;
    let report = BranchProtectionWorkerReport {
        report_id,
        worker_plan_id: plan.worker_plan_id,
        repository: plan.repository.clone(),
        branch: plan.branch.clone(),
        status,
        reconcile_receipt_ids: receipt_ids,
        rejected_reasons,
        report_hash,
        executed_at,
    };
    report.verify()?;
    Ok(report)
}
