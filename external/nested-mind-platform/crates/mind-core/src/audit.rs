use crate::{
    EventId, EventRecord, Identity, MindId, MindResult, ReplayEngine, SignatureRequirement,
    SnapshotRecord,
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReplayAuditMode {
    Full,
    FromSnapshot,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayAuditReport {
    pub mind_id: MindId,
    pub mode: ReplayAuditMode,
    pub event_count: usize,
    pub passed: bool,
    pub signature_requirement: SignatureRequirement,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub final_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub latest_commit_id: Option<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub snapshot_id: Option<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub failure: Option<String>,
}

pub struct ReplayAudit;

impl ReplayAudit {
    #[must_use]
    pub fn audit_full(
        identity: Identity,
        records: &[EventRecord],
        signature_requirement: SignatureRequirement,
    ) -> ReplayAuditReport {
        let mind_id = identity.id;
        match ReplayEngine::replay_with_signature_requirement(
            identity,
            records,
            signature_requirement,
        ) {
            Ok((_, report)) => ReplayAuditReport {
                mind_id,
                mode: ReplayAuditMode::Full,
                event_count: records.len(),
                passed: true,
                signature_requirement,
                final_hash: Some(report.final_hash),
                latest_commit_id: report.latest_commit_id,
                snapshot_id: None,
                failure: None,
            },
            Err(error) => ReplayAuditReport {
                mind_id,
                mode: ReplayAuditMode::Full,
                event_count: records.len(),
                passed: false,
                signature_requirement,
                final_hash: None,
                latest_commit_id: None,
                snapshot_id: None,
                failure: Some(error.to_string()),
            },
        }
    }

    #[must_use]
    pub fn audit_from_snapshot(
        snapshot: &SnapshotRecord,
        tail_records: &[EventRecord],
        signature_requirement: SignatureRequirement,
    ) -> ReplayAuditReport {
        match ReplayEngine::replay_from_snapshot(snapshot, tail_records, signature_requirement) {
            Ok((_, report)) => ReplayAuditReport {
                mind_id: snapshot.mind_id,
                mode: ReplayAuditMode::FromSnapshot,
                event_count: tail_records.len(),
                passed: true,
                signature_requirement,
                final_hash: Some(report.final_hash),
                latest_commit_id: report.latest_commit_id,
                snapshot_id: Some(snapshot.snapshot_id),
                failure: None,
            },
            Err(error) => ReplayAuditReport {
                mind_id: snapshot.mind_id,
                mode: ReplayAuditMode::FromSnapshot,
                event_count: tail_records.len(),
                passed: false,
                signature_requirement,
                final_hash: None,
                latest_commit_id: None,
                snapshot_id: Some(snapshot.snapshot_id),
                failure: Some(error.to_string()),
            },
        }
    }

    pub fn assert_full(
        identity: Identity,
        records: &[EventRecord],
        signature_requirement: SignatureRequirement,
    ) -> MindResult<()> {
        ReplayEngine::replay_with_signature_requirement(identity, records, signature_requirement)
            .map(|_| ())
    }
}
