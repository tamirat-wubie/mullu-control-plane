use crate::{
    ConsensusApplyReport, ConsensusApplyStatus, ConsensusLogCompactionDecision,
    ConsensusPhysicalCompactionPlan, ConsensusPhysicalCompactionReport,
    ConsensusPhysicalCompactionStatus, EventId, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConsensusRetentionEvidenceClass {
    CommitCertificate,
    ApplyReport,
    IdempotencyDecision,
    CompactionDecision,
    PhysicalCompactionReport,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionPolicy {
    pub require_backup_guard: bool,
    pub delete_commit_certificates: bool,
    pub delete_apply_reports: bool,
    pub preserve_rejected_apply_reports: bool,
    pub keep_latest_apply_reports: usize,
}

impl Default for ConsensusRetentionPolicy {
    fn default() -> Self {
        Self {
            require_backup_guard: true,
            delete_commit_certificates: true,
            delete_apply_reports: false,
            preserve_rejected_apply_reports: true,
            keep_latest_apply_reports: 128,
        }
    }
}

impl ConsensusRetentionPolicy {
    pub fn validate(&self) -> MindResult<()> {
        if !self.delete_commit_certificates && !self.delete_apply_reports {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus retention policy would not delete any evidence".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionEnforcementPlan {
    pub plan_id: EventId,
    pub decision_id: EventId,
    pub cluster_id: String,
    pub policy: ConsensusRetentionPolicy,
    #[serde(default)]
    pub certificate_ids_to_delete: Vec<EventId>,
    #[serde(default)]
    pub apply_report_ids_to_delete: Vec<EventId>,
    #[serde(default)]
    pub apply_report_ids_to_keep: Vec<EventId>,
    #[serde(default)]
    pub evidence_classes_preserved: Vec<ConsensusRetentionEvidenceClass>,
    pub backup_guard_hash: String,
    pub created_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusRetentionEnforcementReport {
    pub report_id: EventId,
    pub plan_id: EventId,
    pub decision_id: EventId,
    pub cluster_id: String,
    pub status: ConsensusPhysicalCompactionStatus,
    pub deleted_certificate_count: usize,
    pub deleted_apply_report_count: usize,
    #[serde(default)]
    pub preserved_evidence_classes: Vec<ConsensusRetentionEvidenceClass>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub enforced_at: OffsetDateTime,
}

pub fn plan_consensus_retention_enforcement(
    decision: &ConsensusLogCompactionDecision,
    physical_plan: &ConsensusPhysicalCompactionPlan,
    apply_reports: &[ConsensusApplyReport],
    policy: &ConsensusRetentionPolicy,
) -> MindResult<ConsensusRetentionEnforcementPlan> {
    policy.validate()?;
    if physical_plan.decision_id != decision.compaction_id {
        return Err(MindError::DistributedPlanInvalid {
            reason: "retention plan decision mismatch".to_owned(),
        });
    }
    physical_plan.backup_guard.verify_for(decision)?;
    let compact_certificate_ids: BTreeSet<EventId> =
        decision.compact_certificate_ids.iter().copied().collect();
    let mut eligible_apply_reports = apply_reports
        .iter()
        .filter(|report| report.cluster_id == decision.cluster_id)
        .filter(|report| compact_certificate_ids.contains(&report.certificate_id))
        .filter(|report| {
            !policy.preserve_rejected_apply_reports
                || report.status == ConsensusApplyStatus::Applied
        })
        .collect::<Vec<_>>();
    eligible_apply_reports.sort_by_key(|report| report.applied_at);
    let keep_tail = policy
        .keep_latest_apply_reports
        .min(eligible_apply_reports.len());
    let split_at = eligible_apply_reports.len().saturating_sub(keep_tail);
    let apply_report_ids_to_delete = if policy.delete_apply_reports {
        eligible_apply_reports[..split_at]
            .iter()
            .map(|report| report.apply_id)
            .collect()
    } else {
        Vec::new()
    };
    let apply_report_ids_to_keep = eligible_apply_reports[split_at..]
        .iter()
        .map(|report| report.apply_id)
        .collect();
    let certificate_ids_to_delete = if policy.delete_commit_certificates {
        physical_plan.certificate_ids_to_delete.clone()
    } else {
        Vec::new()
    };
    let mut evidence_classes_preserved = vec![
        ConsensusRetentionEvidenceClass::IdempotencyDecision,
        ConsensusRetentionEvidenceClass::CompactionDecision,
        ConsensusRetentionEvidenceClass::PhysicalCompactionReport,
    ];
    if !policy.delete_apply_reports {
        evidence_classes_preserved.push(ConsensusRetentionEvidenceClass::ApplyReport);
    }
    if !policy.delete_commit_certificates {
        evidence_classes_preserved.push(ConsensusRetentionEvidenceClass::CommitCertificate);
    }
    Ok(ConsensusRetentionEnforcementPlan {
        plan_id: EventId::new(),
        decision_id: decision.compaction_id,
        cluster_id: decision.cluster_id.clone(),
        policy: policy.clone(),
        certificate_ids_to_delete,
        apply_report_ids_to_delete,
        apply_report_ids_to_keep,
        evidence_classes_preserved,
        backup_guard_hash: physical_plan.backup_guard.backup_hash.clone(),
        created_at: OffsetDateTime::now_utc(),
    })
}

#[must_use]
pub fn report_consensus_retention_enforcement_planned(
    plan: &ConsensusRetentionEnforcementPlan,
) -> ConsensusRetentionEnforcementReport {
    let status = if plan.certificate_ids_to_delete.is_empty()
        && plan.apply_report_ids_to_delete.is_empty()
    {
        ConsensusPhysicalCompactionStatus::Skipped
    } else {
        ConsensusPhysicalCompactionStatus::Planned
    };
    ConsensusRetentionEnforcementReport {
        report_id: EventId::new(),
        plan_id: plan.plan_id,
        decision_id: plan.decision_id,
        cluster_id: plan.cluster_id.clone(),
        status,
        deleted_certificate_count: 0,
        deleted_apply_report_count: 0,
        preserved_evidence_classes: plan.evidence_classes_preserved.clone(),
        reasons: vec!["consensus retention enforcement planned with backup guard".to_owned()],
        enforced_at: OffsetDateTime::now_utc(),
    }
}

#[must_use]
pub fn report_consensus_retention_enforcement_applied(
    plan: &ConsensusRetentionEnforcementPlan,
    deleted_certificate_count: usize,
    deleted_apply_report_count: usize,
) -> ConsensusRetentionEnforcementReport {
    ConsensusRetentionEnforcementReport {
        report_id: EventId::new(),
        plan_id: plan.plan_id,
        decision_id: plan.decision_id,
        cluster_id: plan.cluster_id.clone(),
        status: ConsensusPhysicalCompactionStatus::Applied,
        deleted_certificate_count,
        deleted_apply_report_count,
        preserved_evidence_classes: plan.evidence_classes_preserved.clone(),
        reasons: vec![
            "consensus retention enforcement applied after backup guard verification".to_owned(),
        ],
        enforced_at: OffsetDateTime::now_utc(),
    }
}

#[must_use]
pub fn derive_retention_report_from_physical_report(
    physical_report: &ConsensusPhysicalCompactionReport,
) -> ConsensusRetentionEnforcementReport {
    ConsensusRetentionEnforcementReport {
        report_id: EventId::new(),
        plan_id: physical_report.plan_id,
        decision_id: physical_report.decision_id,
        cluster_id: physical_report.cluster_id.clone(),
        status: physical_report.status,
        deleted_certificate_count: physical_report.deleted_certificate_count,
        deleted_apply_report_count: physical_report.deleted_apply_report_count,
        preserved_evidence_classes: vec![
            ConsensusRetentionEvidenceClass::ApplyReport,
            ConsensusRetentionEvidenceClass::IdempotencyDecision,
            ConsensusRetentionEvidenceClass::CompactionDecision,
            ConsensusRetentionEvidenceClass::PhysicalCompactionReport,
        ],
        reasons: physical_report.reasons.clone(),
        enforced_at: OffsetDateTime::now_utc(),
    }
}
