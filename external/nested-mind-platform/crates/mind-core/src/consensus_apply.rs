use crate::{
    apply_replication_batch, ConsensusCommitCertificate, ConsensusMembership, EventId, MindError,
    MindId, MindResult, ReplicatedEventStore, ReplicationApplyReport, ReplicationBatch,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConsensusApplyStatus {
    Applied,
    Rejected,
    Skipped,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusApplyReport {
    pub apply_id: EventId,
    pub certificate_id: EventId,
    pub entry_id: EventId,
    pub cluster_id: String,
    pub operation_kind: String,
    pub operation_hash: String,
    pub committed: bool,
    pub status: ConsensusApplyStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    pub records_appended: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    pub applied_at: OffsetDateTime,
}

impl ConsensusApplyReport {
    #[must_use]
    pub fn rejected(certificate: &ConsensusCommitCertificate, error: impl Into<String>) -> Self {
        Self {
            apply_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            cluster_id: certificate.entry.cluster_id.clone(),
            operation_kind: certificate.entry.operation_kind.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            committed: certificate.committed,
            status: ConsensusApplyStatus::Rejected,
            mind_id: None,
            records_appended: 0,
            error: Some(error.into()),
            applied_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn skipped(certificate: &ConsensusCommitCertificate) -> Self {
        Self {
            apply_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            cluster_id: certificate.entry.cluster_id.clone(),
            operation_kind: certificate.entry.operation_kind.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            committed: certificate.committed,
            status: ConsensusApplyStatus::Skipped,
            mind_id: None,
            records_appended: 0,
            error: None,
            applied_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn from_replication_apply(
        certificate: &ConsensusCommitCertificate,
        report: &ReplicationApplyReport,
    ) -> Self {
        Self {
            apply_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            cluster_id: certificate.entry.cluster_id.clone(),
            operation_kind: certificate.entry.operation_kind.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            committed: certificate.committed,
            status: if report.accepted {
                ConsensusApplyStatus::Applied
            } else {
                ConsensusApplyStatus::Rejected
            },
            mind_id: Some(report.mind_id),
            records_appended: report.appended_records,
            error: report.error.clone(),
            applied_at: OffsetDateTime::now_utc(),
        }
    }
}

pub fn plan_consensus_apply(
    membership: &ConsensusMembership,
    certificate: &ConsensusCommitCertificate,
) -> MindResult<ConsensusApplyReport> {
    certificate.verify(membership)?;
    if !certificate.committed {
        return Ok(ConsensusApplyReport::rejected(
            certificate,
            "consensus certificate is not committed",
        ));
    }
    if certificate.entry.operation_kind != "replication_batch_commit" {
        return Ok(ConsensusApplyReport::skipped(certificate));
    }
    let batch: ReplicationBatch = serde_json::from_str(&certificate.entry.operation_json)?;
    Ok(ConsensusApplyReport {
        apply_id: EventId::new(),
        certificate_id: certificate.certificate_id,
        entry_id: certificate.entry.entry_id,
        cluster_id: certificate.entry.cluster_id.clone(),
        operation_kind: certificate.entry.operation_kind.clone(),
        operation_hash: certificate.entry.operation_hash.clone(),
        committed: certificate.committed,
        status: ConsensusApplyStatus::Skipped,
        mind_id: Some(batch.mind_id),
        records_appended: 0,
        error: None,
        applied_at: OffsetDateTime::now_utc(),
    })
}

pub fn apply_certified_replication_batch<S: ReplicatedEventStore>(
    store: &mut S,
    membership: &ConsensusMembership,
    certificate: &ConsensusCommitCertificate,
    follower_id: impl Into<String>,
) -> MindResult<ConsensusApplyReport> {
    certificate.verify(membership)?;
    if !certificate.committed {
        return Ok(ConsensusApplyReport::rejected(
            certificate,
            "consensus certificate is not committed",
        ));
    }
    if certificate.entry.operation_kind != "replication_batch_commit" {
        return Err(MindError::DistributedPlanInvalid {
            reason: "only replication_batch_commit is executable by this apply path".to_owned(),
        });
    }
    let batch: ReplicationBatch = serde_json::from_str(&certificate.entry.operation_json)?;
    let report = apply_replication_batch(store, follower_id, &batch)?;
    Ok(ConsensusApplyReport::from_replication_apply(
        certificate,
        &report,
    ))
}
