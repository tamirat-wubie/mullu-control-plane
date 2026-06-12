use crate::{
    hash_serializable, AppendOnlyEventStore, EventId, EventRecord, MindError, MindId, MindResult,
    ReplicatedEventStore, ReplicationAck, ReplicationBatch, ReplicationCursor, ReplicationTerm,
    SignatureRequirement,
};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::PathBuf,
};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationEndpoint {
    pub node_id: String,
    pub base_url: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub shared_secret_ref: Option<String>,
}

impl ReplicationEndpoint {
    #[must_use]
    pub fn new(node_id: impl Into<String>, base_url: impl Into<String>) -> Self {
        Self {
            node_id: node_id.into(),
            base_url: base_url.into(),
            shared_secret_ref: None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationTransportPlan {
    pub leader_id: String,
    pub term: ReplicationTerm,
    #[serde(default)]
    pub followers: Vec<ReplicationEndpoint>,
    pub push_path: String,
    pub max_records_per_batch: usize,
    pub required_acks: usize,
}

impl ReplicationTransportPlan {
    #[must_use]
    pub fn new(
        leader_id: impl Into<String>,
        followers: Vec<ReplicationEndpoint>,
        required_acks: usize,
    ) -> Self {
        let leader_id = leader_id.into();
        Self {
            term: ReplicationTerm::new(1, leader_id.clone()),
            leader_id,
            followers,
            push_path: "/system/replication/follower/batches".to_owned(),
            max_records_per_batch: 100,
            required_acks: required_acks.max(1),
        }
    }

    pub fn validate(&self) -> MindResult<()> {
        if self.leader_id.trim().is_empty() {
            return Err(MindError::DistributedPlanInvalid {
                reason: "replication leader id is required".to_owned(),
            });
        }
        if self.required_acks == 0 {
            return Err(MindError::DistributedPlanInvalid {
                reason: "replication required_acks must be greater than zero".to_owned(),
            });
        }
        if self.required_acks > self.followers.len().max(1) {
            return Err(MindError::QuorumNotMet {
                required: self.required_acks,
                accepted: self.followers.len(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplicationEnvelope {
    pub envelope_id: EventId,
    pub batch: ReplicationBatch,
    pub body_hash: String,
    pub sent_at: OffsetDateTime,
}

impl ReplicationEnvelope {
    pub fn from_batch(batch: ReplicationBatch) -> MindResult<Self> {
        let body_hash = hash_serializable(&batch)?;
        Ok(Self {
            envelope_id: EventId::new(),
            batch,
            body_hash,
            sent_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn verify(&self) -> MindResult<()> {
        let expected = hash_serializable(&self.batch)?;
        if expected != self.body_hash {
            return Err(MindError::DistributedAppendRejected {
                reason: "replication envelope hash mismatch".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationApplyReport {
    pub batch_id: EventId,
    pub mind_id: MindId,
    pub accepted: bool,
    pub appended_records: usize,
    pub next_sequence: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_record_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl ReplicationApplyReport {
    #[must_use]
    pub fn from_ack(
        batch: &ReplicationBatch,
        ack: &ReplicationAck,
        appended_records: usize,
    ) -> Self {
        Self {
            batch_id: batch.batch_id,
            mind_id: batch.mind_id,
            accepted: ack.accepted,
            appended_records,
            next_sequence: ack.next_sequence,
            last_record_hash: ack.last_record_hash.clone(),
            error: ack.error.clone(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct JsonlReplicationInbox {
    path: PathBuf,
}

impl JsonlReplicationInbox {
    pub fn new(path: impl Into<PathBuf>) -> MindResult<Self> {
        let path = path.into();
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)?;
            }
        }
        Ok(Self { path })
    }

    pub fn append_envelope(&self, envelope: &ReplicationEnvelope) -> MindResult<()> {
        envelope.verify()?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{}", serde_json::to_string(envelope)?)?;
        file.flush()?;
        file.sync_data()?;
        Ok(())
    }

    pub fn envelopes(&self) -> MindResult<Vec<ReplicationEnvelope>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }
        let file = OpenOptions::new().read(true).open(&self.path)?;
        let reader = BufReader::new(file);
        let mut envelopes = Vec::new();
        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let envelope = serde_json::from_str::<ReplicationEnvelope>(&line)?;
            envelope.verify()?;
            envelopes.push(envelope);
        }
        Ok(envelopes)
    }
}

pub fn cursor_from_store<S: AppendOnlyEventStore>(
    store: &S,
    mind_id: MindId,
) -> MindResult<ReplicationCursor> {
    let records = store.records_for_mind(mind_id)?;
    Ok(records.last().map_or_else(
        || ReplicationCursor::start(mind_id),
        ReplicationCursor::after,
    ))
}

pub fn apply_replication_batch<S: ReplicatedEventStore>(
    store: &mut S,
    follower_id: impl Into<String>,
    batch: &ReplicationBatch,
) -> MindResult<ReplicationApplyReport> {
    let cursor = cursor_from_store(store, batch.mind_id)?;
    let requirement = store.signature_requirement();
    let follower = crate::FollowerReplicationProtocol::new(follower_id, cursor, requirement);
    let ack = follower.validate_batch(batch)?;
    if !ack.accepted {
        return Ok(ReplicationApplyReport::from_ack(batch, &ack, 0));
    }
    let appended = store.append_replicated_records(batch.records.clone())?;
    Ok(ReplicationApplyReport::from_ack(batch, &ack, appended))
}

pub fn verify_records_for_replication(
    records: &[EventRecord],
    requirement: SignatureRequirement,
) -> MindResult<()> {
    crate::verify_record_chain_with_signatures(records, requirement)
}
