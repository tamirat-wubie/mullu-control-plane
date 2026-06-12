use crate::{
    BackupVerificationReport, ConsensusLogCompactionDecision, EventId, MindError, MindResult,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConsensusPhysicalCompactionStatus {
    Skipped,
    Planned,
    Applied,
    Rejected,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusCompactionBackupGuard {
    pub guard_id: EventId,
    pub decision_id: EventId,
    pub backup_id: EventId,
    pub backup_hash: String,
    pub backup_event_count: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub latest_event_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub high_watermark_entry_hash: Option<String>,
    pub verified_at: OffsetDateTime,
}

impl ConsensusCompactionBackupGuard {
    pub fn from_backup_verification(
        decision: &ConsensusLogCompactionDecision,
        verification: &BackupVerificationReport,
    ) -> MindResult<Self> {
        if !verification.valid {
            return Err(MindError::BackupManifestMismatch);
        }
        if decision.should_compact && decision.high_watermark_entry_hash.is_none() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "physical consensus compaction requires a high-watermark hash".to_owned(),
            });
        }
        Ok(Self {
            guard_id: EventId::new(),
            decision_id: decision.compaction_id,
            backup_id: verification.backup_id,
            backup_hash: verification.backup_hash.clone(),
            backup_event_count: verification.event_count,
            latest_event_hash: verification.latest_event_hash.clone(),
            high_watermark_entry_hash: decision.high_watermark_entry_hash.clone(),
            verified_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn verify_for(&self, decision: &ConsensusLogCompactionDecision) -> MindResult<()> {
        if self.decision_id != decision.compaction_id {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus compaction backup guard decision mismatch".to_owned(),
            });
        }
        if self.backup_hash.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus compaction backup guard missing backup hash".to_owned(),
            });
        }
        if self.high_watermark_entry_hash != decision.high_watermark_entry_hash {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus compaction high-watermark hash mismatch".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusPhysicalCompactionPlan {
    pub plan_id: EventId,
    pub decision_id: EventId,
    pub cluster_id: String,
    pub backup_guard: ConsensusCompactionBackupGuard,
    #[serde(default)]
    pub certificate_ids_to_delete: Vec<EventId>,
    #[serde(default)]
    pub certificate_ids_to_keep: Vec<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub high_watermark_entry_id: Option<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub high_watermark_entry_hash: Option<String>,
    pub created_at: OffsetDateTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusPhysicalCompactionReport {
    pub report_id: EventId,
    pub plan_id: EventId,
    pub decision_id: EventId,
    pub cluster_id: String,
    pub status: ConsensusPhysicalCompactionStatus,
    pub backup_guard: ConsensusCompactionBackupGuard,
    pub deleted_certificate_count: usize,
    pub deleted_apply_report_count: usize,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub compacted_at: OffsetDateTime,
}

impl ConsensusPhysicalCompactionReport {
    #[must_use]
    pub fn planned(plan: &ConsensusPhysicalCompactionPlan) -> Self {
        Self {
            report_id: EventId::new(),
            plan_id: plan.plan_id,
            decision_id: plan.decision_id,
            cluster_id: plan.cluster_id.clone(),
            status: if plan.certificate_ids_to_delete.is_empty() {
                ConsensusPhysicalCompactionStatus::Skipped
            } else {
                ConsensusPhysicalCompactionStatus::Planned
            },
            backup_guard: plan.backup_guard.clone(),
            deleted_certificate_count: 0,
            deleted_apply_report_count: 0,
            reasons: if plan.certificate_ids_to_delete.is_empty() {
                vec!["compaction decision did not select certificates for deletion".to_owned()]
            } else {
                vec!["backup guard satisfied; physical deletion can be executed".to_owned()]
            },
            compacted_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn applied(
        plan: &ConsensusPhysicalCompactionPlan,
        deleted_certificate_count: usize,
        deleted_apply_report_count: usize,
    ) -> Self {
        Self {
            report_id: EventId::new(),
            plan_id: plan.plan_id,
            decision_id: plan.decision_id,
            cluster_id: plan.cluster_id.clone(),
            status: ConsensusPhysicalCompactionStatus::Applied,
            backup_guard: plan.backup_guard.clone(),
            deleted_certificate_count,
            deleted_apply_report_count,
            reasons: vec![
                "physical consensus log compaction applied after backup guard verification"
                    .to_owned(),
            ],
            compacted_at: OffsetDateTime::now_utc(),
        }
    }
}

pub fn plan_physical_consensus_compaction(
    decision: &ConsensusLogCompactionDecision,
    backup_guard: ConsensusCompactionBackupGuard,
) -> MindResult<ConsensusPhysicalCompactionPlan> {
    backup_guard.verify_for(decision)?;
    Ok(ConsensusPhysicalCompactionPlan {
        plan_id: EventId::new(),
        decision_id: decision.compaction_id,
        cluster_id: decision.cluster_id.clone(),
        backup_guard,
        certificate_ids_to_delete: decision.compact_certificate_ids.clone(),
        certificate_ids_to_keep: decision.keep_certificate_ids.clone(),
        high_watermark_entry_id: decision.high_watermark_entry_id,
        high_watermark_entry_hash: decision.high_watermark_entry_hash.clone(),
        created_at: OffsetDateTime::now_utc(),
    })
}
