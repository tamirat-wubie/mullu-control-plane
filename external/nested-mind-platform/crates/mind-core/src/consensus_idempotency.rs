use crate::{
    apply_certified_replication_batch, ConsensusApplyReport, ConsensusApplyStatus,
    ConsensusCommitCertificate, ConsensusMembership, EventId, MindError, MindResult,
    ReplicatedEventStore,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum ConsensusApplyIdempotencyStatus {
    Ready,
    AlreadyApplied,
    Conflict,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusApplyIdempotencyDecision {
    pub decision_id: EventId,
    pub certificate_id: EventId,
    pub entry_id: EventId,
    pub entry_hash: String,
    pub operation_hash: String,
    pub status: ConsensusApplyIdempotencyStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub matched_apply_id: Option<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    pub checked_at: OffsetDateTime,
}

impl ConsensusApplyIdempotencyDecision {
    #[must_use]
    pub fn ready(certificate: &ConsensusCommitCertificate) -> Self {
        Self {
            decision_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            entry_hash: certificate.entry.entry_hash.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            status: ConsensusApplyIdempotencyStatus::Ready,
            matched_apply_id: None,
            reason: None,
            checked_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn already_applied(
        certificate: &ConsensusCommitCertificate,
        report: &ConsensusApplyReport,
    ) -> Self {
        Self {
            decision_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            entry_hash: certificate.entry.entry_hash.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            status: ConsensusApplyIdempotencyStatus::AlreadyApplied,
            matched_apply_id: Some(report.apply_id),
            reason: Some("matching committed entry was already applied".to_owned()),
            checked_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn conflict(
        certificate: &ConsensusCommitCertificate,
        report: &ConsensusApplyReport,
        reason: impl Into<String>,
    ) -> Self {
        Self {
            decision_id: EventId::new(),
            certificate_id: certificate.certificate_id,
            entry_id: certificate.entry.entry_id,
            entry_hash: certificate.entry.entry_hash.clone(),
            operation_hash: certificate.entry.operation_hash.clone(),
            status: ConsensusApplyIdempotencyStatus::Conflict,
            matched_apply_id: Some(report.apply_id),
            reason: Some(reason.into()),
            checked_at: OffsetDateTime::now_utc(),
        }
    }
}

#[must_use]
pub fn evaluate_consensus_apply_idempotency(
    certificate: &ConsensusCommitCertificate,
    prior_reports: &[ConsensusApplyReport],
) -> ConsensusApplyIdempotencyDecision {
    for report in prior_reports {
        if report.entry_id == certificate.entry.entry_id
            && report.operation_hash != certificate.entry.operation_hash
        {
            return ConsensusApplyIdempotencyDecision::conflict(
                certificate,
                report,
                "same consensus entry id was recorded with a different operation hash",
            );
        }
        if report.certificate_id == certificate.certificate_id
            && report.operation_hash == certificate.entry.operation_hash
            && report.status == ConsensusApplyStatus::Applied
        {
            return ConsensusApplyIdempotencyDecision::already_applied(certificate, report);
        }
    }
    ConsensusApplyIdempotencyDecision::ready(certificate)
}

pub fn apply_certified_replication_batch_idempotent<S: ReplicatedEventStore>(
    store: &mut S,
    membership: &ConsensusMembership,
    certificate: &ConsensusCommitCertificate,
    prior_reports: &[ConsensusApplyReport],
    follower_id: impl Into<String>,
) -> MindResult<(ConsensusApplyIdempotencyDecision, ConsensusApplyReport)> {
    let decision = evaluate_consensus_apply_idempotency(certificate, prior_reports);
    match decision.status {
        ConsensusApplyIdempotencyStatus::Ready => {
            let report =
                apply_certified_replication_batch(store, membership, certificate, follower_id)?;
            Ok((decision, report))
        }
        ConsensusApplyIdempotencyStatus::AlreadyApplied => {
            Ok((decision, ConsensusApplyReport::skipped(certificate)))
        }
        ConsensusApplyIdempotencyStatus::Conflict => Err(MindError::DistributedPlanInvalid {
            reason: decision
                .reason
                .clone()
                .unwrap_or_else(|| "consensus apply idempotency conflict".to_owned()),
        }),
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusLogCompactionPolicy {
    pub keep_latest_committed: usize,
    pub min_committed_entries_between_compactions: usize,
}

impl Default for ConsensusLogCompactionPolicy {
    fn default() -> Self {
        Self {
            keep_latest_committed: 64,
            min_committed_entries_between_compactions: 128,
        }
    }
}

impl ConsensusLogCompactionPolicy {
    pub fn validate(&self) -> MindResult<()> {
        if self.keep_latest_committed == 0 {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus compaction must keep at least one committed certificate"
                    .to_owned(),
            });
        }
        if self.min_committed_entries_between_compactions == 0 {
            return Err(MindError::DistributedPlanInvalid {
                reason: "consensus compaction minimum interval must be greater than zero"
                    .to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusLogCompactionDecision {
    pub compaction_id: EventId,
    pub cluster_id: String,
    pub policy: ConsensusLogCompactionPolicy,
    pub committed_count: usize,
    pub should_compact: bool,
    #[serde(default)]
    pub keep_certificate_ids: Vec<EventId>,
    #[serde(default)]
    pub compact_certificate_ids: Vec<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub high_watermark_entry_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub high_watermark_entry_id: Option<EventId>,
    #[serde(default)]
    pub reasons: Vec<String>,
    pub decided_at: OffsetDateTime,
}

pub fn evaluate_consensus_log_compaction(
    cluster_id: impl Into<String>,
    certificates: &[ConsensusCommitCertificate],
    applied_reports: &[ConsensusApplyReport],
    policy: &ConsensusLogCompactionPolicy,
) -> MindResult<ConsensusLogCompactionDecision> {
    policy.validate()?;
    let cluster_id = cluster_id.into();
    let applied_entry_ids: BTreeSet<EventId> = applied_reports
        .iter()
        .filter(|report| report.status == ConsensusApplyStatus::Applied)
        .map(|report| report.entry_id)
        .collect();
    let mut committed = certificates
        .iter()
        .filter(|certificate| certificate.committed)
        .filter(|certificate| certificate.entry.cluster_id == cluster_id)
        .filter(|certificate| applied_entry_ids.contains(&certificate.entry.entry_id))
        .cloned()
        .collect::<Vec<_>>();
    committed.sort_by_key(|certificate| certificate.certified_at);
    let committed_count = committed.len();
    let should_compact = committed_count
        >= policy.keep_latest_committed + policy.min_committed_entries_between_compactions;
    let split_at = committed_count.saturating_sub(policy.keep_latest_committed);
    let compact = if should_compact {
        committed[..split_at].to_vec()
    } else {
        Vec::new()
    };
    let keep = if should_compact {
        committed[split_at..].to_vec()
    } else {
        committed
    };
    let high_watermark = compact.last();
    let mut reasons = Vec::new();
    if should_compact {
        reasons.push("committed applied consensus entries exceeded retention policy".to_owned());
    } else {
        reasons
            .push("committed applied consensus entries are below compaction threshold".to_owned());
    }
    Ok(ConsensusLogCompactionDecision {
        compaction_id: EventId::new(),
        cluster_id,
        policy: policy.clone(),
        committed_count,
        should_compact,
        keep_certificate_ids: keep
            .iter()
            .map(|certificate| certificate.certificate_id)
            .collect(),
        compact_certificate_ids: compact
            .iter()
            .map(|certificate| certificate.certificate_id)
            .collect(),
        high_watermark_entry_hash: high_watermark
            .map(|certificate| certificate.entry.entry_hash.clone()),
        high_watermark_entry_id: high_watermark.map(|certificate| certificate.entry.entry_id),
        reasons,
        decided_at: OffsetDateTime::now_utc(),
    })
}
