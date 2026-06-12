use crate::{
    hash_serializable, verify_record_tail_with_signatures, EventId, EventRecord, MindError, MindId,
    MindResult, SignatureRequirement,
};
use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationCursor {
    pub mind_id: MindId,
    pub next_sequence: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub previous_record_hash: Option<String>,
}

impl ReplicationCursor {
    #[must_use]
    pub fn start(mind_id: MindId) -> Self {
        Self {
            mind_id,
            next_sequence: 1,
            previous_record_hash: None,
        }
    }

    #[must_use]
    pub fn after(record: &EventRecord) -> Self {
        Self {
            mind_id: record.mind_id,
            next_sequence: record.sequence + 1,
            previous_record_hash: Some(record.record_hash.clone()),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationTerm {
    pub term: u64,
    pub leader_id: String,
    pub epoch_id: EventId,
}

impl ReplicationTerm {
    #[must_use]
    pub fn new(term: u64, leader_id: impl Into<String>) -> Self {
        Self {
            term,
            leader_id: leader_id.into(),
            epoch_id: EventId::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplicationBatch {
    pub batch_id: EventId,
    pub term: ReplicationTerm,
    pub mind_id: MindId,
    pub from_sequence: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub previous_record_hash: Option<String>,
    #[serde(default)]
    pub records: Vec<EventRecord>,
    pub batch_hash: String,
    pub produced_at: OffsetDateTime,
}

impl ReplicationBatch {
    pub fn new(
        term: ReplicationTerm,
        cursor: ReplicationCursor,
        records: Vec<EventRecord>,
        requirement: SignatureRequirement,
    ) -> MindResult<Self> {
        verify_records_match_cursor(&cursor, &records, requirement)?;
        let batch_hash = calculate_batch_hash(
            &term,
            cursor.mind_id,
            cursor.next_sequence,
            &cursor.previous_record_hash,
            &records,
        )?;
        Ok(Self {
            batch_id: EventId::new(),
            term,
            mind_id: cursor.mind_id,
            from_sequence: cursor.next_sequence,
            previous_record_hash: cursor.previous_record_hash,
            records,
            batch_hash,
            produced_at: OffsetDateTime::now_utc(),
        })
    }

    pub fn verify(
        &self,
        cursor: &ReplicationCursor,
        requirement: SignatureRequirement,
    ) -> MindResult<()> {
        if self.mind_id != cursor.mind_id {
            return Err(MindError::DistributedAppendRejected {
                reason: "replication batch mind id does not match follower cursor".to_owned(),
            });
        }
        if self.from_sequence != cursor.next_sequence {
            return Err(MindError::EventSequenceGap {
                expected: cursor.next_sequence,
                actual: self.from_sequence,
            });
        }
        if self.previous_record_hash != cursor.previous_record_hash {
            return Err(MindError::EventChainBroken {
                sequence: self.from_sequence,
                expected: cursor.previous_record_hash.clone(),
                actual: self.previous_record_hash.clone(),
            });
        }
        verify_records_match_cursor(cursor, &self.records, requirement)?;
        let expected = calculate_batch_hash(
            &self.term,
            self.mind_id,
            self.from_sequence,
            &self.previous_record_hash,
            &self.records,
        )?;
        if expected != self.batch_hash {
            return Err(MindError::DistributedAppendRejected {
                reason: "replication batch hash mismatch".to_owned(),
            });
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationAck {
    pub batch_id: EventId,
    pub follower_id: String,
    pub accepted: bool,
    pub next_sequence: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_record_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    pub acknowledged_at: OffsetDateTime,
}

impl ReplicationAck {
    #[must_use]
    pub fn accepted(batch: &ReplicationBatch, follower_id: impl Into<String>) -> Self {
        let next_sequence = batch
            .records
            .last()
            .map_or(batch.from_sequence, |record| record.sequence + 1);
        let last_record_hash = batch
            .records
            .last()
            .map(|record| record.record_hash.clone())
            .or_else(|| batch.previous_record_hash.clone());
        Self {
            batch_id: batch.batch_id,
            follower_id: follower_id.into(),
            accepted: true,
            next_sequence,
            last_record_hash,
            error: None,
            acknowledged_at: OffsetDateTime::now_utc(),
        }
    }

    #[must_use]
    pub fn rejected(
        batch_id: EventId,
        follower_id: impl Into<String>,
        next_sequence: u64,
        error: impl Into<String>,
    ) -> Self {
        Self {
            batch_id,
            follower_id: follower_id.into(),
            accepted: false,
            next_sequence,
            last_record_hash: None,
            error: Some(error.into()),
            acknowledged_at: OffsetDateTime::now_utc(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationQuorumReport {
    pub batch_id: EventId,
    pub required_acks: usize,
    pub accepted_acks: usize,
    pub rejected_acks: usize,
    pub committed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct LeaderReplicationProtocol {
    pub term: ReplicationTerm,
    pub max_records_per_batch: usize,
    pub required_acks: usize,
}

impl LeaderReplicationProtocol {
    #[must_use]
    pub fn new(term: ReplicationTerm, max_records_per_batch: usize, required_acks: usize) -> Self {
        Self {
            term,
            max_records_per_batch: max_records_per_batch.max(1),
            required_acks: required_acks.max(1),
        }
    }

    pub fn prepare_batch(
        &self,
        cursor: ReplicationCursor,
        all_records: &[EventRecord],
        requirement: SignatureRequirement,
    ) -> MindResult<ReplicationBatch> {
        let records: Vec<EventRecord> = all_records
            .iter()
            .filter(|record| {
                record.mind_id == cursor.mind_id && record.sequence >= cursor.next_sequence
            })
            .take(self.max_records_per_batch)
            .cloned()
            .collect();
        ReplicationBatch::new(self.term.clone(), cursor, records, requirement)
    }

    pub fn evaluate_acks(
        &self,
        batch: &ReplicationBatch,
        acks: &[ReplicationAck],
    ) -> MindResult<ReplicationQuorumReport> {
        let accepted_acks = acks
            .iter()
            .filter(|ack| ack.batch_id == batch.batch_id && ack.accepted)
            .count();
        let rejected_acks = acks
            .iter()
            .filter(|ack| ack.batch_id == batch.batch_id && !ack.accepted)
            .count();
        if accepted_acks < self.required_acks {
            return Ok(ReplicationQuorumReport {
                batch_id: batch.batch_id,
                required_acks: self.required_acks,
                accepted_acks,
                rejected_acks,
                committed: false,
            });
        }
        Ok(ReplicationQuorumReport {
            batch_id: batch.batch_id,
            required_acks: self.required_acks,
            accepted_acks,
            rejected_acks,
            committed: true,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FollowerReplicationProtocol {
    pub follower_id: String,
    pub cursor: ReplicationCursor,
    pub signature_requirement: SignatureRequirement,
}

impl FollowerReplicationProtocol {
    #[must_use]
    pub fn new(
        follower_id: impl Into<String>,
        cursor: ReplicationCursor,
        signature_requirement: SignatureRequirement,
    ) -> Self {
        Self {
            follower_id: follower_id.into(),
            cursor,
            signature_requirement,
        }
    }

    pub fn validate_batch(&self, batch: &ReplicationBatch) -> MindResult<ReplicationAck> {
        match batch.verify(&self.cursor, self.signature_requirement) {
            Ok(()) => Ok(ReplicationAck::accepted(batch, self.follower_id.clone())),
            Err(error) => Ok(ReplicationAck::rejected(
                batch.batch_id,
                self.follower_id.clone(),
                self.cursor.next_sequence,
                error.to_string(),
            )),
        }
    }
}

fn verify_records_match_cursor(
    cursor: &ReplicationCursor,
    records: &[EventRecord],
    requirement: SignatureRequirement,
) -> MindResult<()> {
    if records.is_empty() {
        return Ok(());
    }
    if records
        .iter()
        .any(|record| record.mind_id != cursor.mind_id)
    {
        return Err(MindError::DistributedAppendRejected {
            reason: "replication batch contains records for a different mind".to_owned(),
        });
    }
    verify_record_tail_with_signatures(
        records,
        cursor.next_sequence,
        cursor.previous_record_hash.clone(),
        requirement,
    )
}

fn calculate_batch_hash(
    term: &ReplicationTerm,
    mind_id: MindId,
    from_sequence: u64,
    previous_record_hash: &Option<String>,
    records: &[EventRecord],
) -> MindResult<String> {
    hash_serializable(&ReplicationBatchBody {
        term,
        mind_id,
        from_sequence,
        previous_record_hash,
        records,
    })
}

#[derive(Serialize)]
struct ReplicationBatchBody<'a> {
    term: &'a ReplicationTerm,
    mind_id: MindId,
    from_sequence: u64,
    previous_record_hash: &'a Option<String>,
    records: &'a [EventRecord],
}
