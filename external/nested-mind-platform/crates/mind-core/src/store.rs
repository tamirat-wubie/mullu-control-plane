use crate::{hash_serializable, Commit, EventId, MindError, MindId, MindResult};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SignatureRequirement {
    Optional,
    Required,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EventRecord {
    pub sequence: u64,
    pub mind_id: MindId,
    pub commit_id: EventId,
    pub previous_record_hash: Option<String>,
    pub record_hash: String,
    pub commit: Commit,
}

impl EventRecord {
    pub fn new(
        sequence: u64,
        previous_record_hash: Option<String>,
        commit: Commit,
    ) -> MindResult<Self> {
        let mind_id = commit.mind_id;
        let commit_id = commit.id;
        let record_hash =
            calculate_record_hash(sequence, mind_id, commit_id, &previous_record_hash, &commit)?;
        Ok(Self {
            sequence,
            mind_id,
            commit_id,
            previous_record_hash,
            record_hash,
            commit,
        })
    }
    pub fn calculated_hash(&self) -> MindResult<String> {
        calculate_record_hash(
            self.sequence,
            self.mind_id,
            self.commit_id,
            &self.previous_record_hash,
            &self.commit,
        )
    }
}

#[derive(Serialize)]
struct EventRecordBody<'a> {
    sequence: u64,
    mind_id: MindId,
    commit_id: EventId,
    previous_record_hash: &'a Option<String>,
    commit: &'a Commit,
}

fn calculate_record_hash(
    sequence: u64,
    mind_id: MindId,
    commit_id: EventId,
    previous_record_hash: &Option<String>,
    commit: &Commit,
) -> MindResult<String> {
    hash_serializable(&EventRecordBody {
        sequence,
        mind_id,
        commit_id,
        previous_record_hash,
        commit,
    })
}

pub trait AppendOnlyEventStore {
    fn append(&mut self, commit: Commit) -> MindResult<EventRecord>;
    fn records_for_mind(&self, mind_id: MindId) -> MindResult<Vec<EventRecord>>;
    fn all_records(&self) -> MindResult<Vec<EventRecord>>;
    fn signature_requirement(&self) -> SignatureRequirement {
        SignatureRequirement::Optional
    }
}

/// Append leader-produced event records without recalculating sequence or record hash.
///
/// This is deliberately separate from `AppendOnlyEventStore::append`: leaders append commits,
/// followers ingest already-formed records after verifying the hash chain and signatures.
pub trait ReplicatedEventStore: AppendOnlyEventStore {
    fn append_replicated_records(&mut self, records: Vec<EventRecord>) -> MindResult<usize>;
}

#[derive(Clone, Debug)]
pub struct InMemoryEventStore {
    records: Vec<EventRecord>,
    signature_requirement: SignatureRequirement,
}
impl Default for InMemoryEventStore {
    fn default() -> Self {
        Self {
            records: Vec::new(),
            signature_requirement: SignatureRequirement::Optional,
        }
    }
}
impl InMemoryEventStore {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }
    #[must_use]
    pub fn with_signature_requirement(mut self, requirement: SignatureRequirement) -> Self {
        self.signature_requirement = requirement;
        self
    }
}
impl AppendOnlyEventStore for InMemoryEventStore {
    fn append(&mut self, commit: Commit) -> MindResult<EventRecord> {
        validate_commit_for_append(&commit, self.signature_requirement)?;
        let prior_records = self.records_for_mind(commit.mind_id)?;
        let sequence = prior_records.last().map_or(1, |r| r.sequence + 1);
        let previous_record_hash = prior_records.last().map(|r| r.record_hash.clone());
        let record = EventRecord::new(sequence, previous_record_hash, commit)?;
        self.records.push(record.clone());
        Ok(record)
    }
    fn records_for_mind(&self, mind_id: MindId) -> MindResult<Vec<EventRecord>> {
        Ok(self
            .records
            .iter()
            .filter(|r| r.mind_id == mind_id)
            .cloned()
            .collect())
    }
    fn all_records(&self) -> MindResult<Vec<EventRecord>> {
        Ok(self.records.clone())
    }
    fn signature_requirement(&self) -> SignatureRequirement {
        self.signature_requirement
    }
}

impl ReplicatedEventStore for InMemoryEventStore {
    fn append_replicated_records(&mut self, records: Vec<EventRecord>) -> MindResult<usize> {
        if records.is_empty() {
            return Ok(0);
        }
        let mind_id = records[0].mind_id;
        if records.iter().any(|record| record.mind_id != mind_id) {
            return Err(MindError::DistributedAppendRejected {
                reason: "replicated records contain multiple mind ids".to_owned(),
            });
        }
        let prior_records = self.records_for_mind(mind_id)?;
        let expected_sequence = prior_records.last().map_or(1, |record| record.sequence + 1);
        let expected_previous_hash = prior_records
            .last()
            .map(|record| record.record_hash.clone());
        verify_record_tail_with_signatures(
            &records,
            expected_sequence,
            expected_previous_hash,
            self.signature_requirement,
        )?;
        let count = records.len();
        self.records.extend(records);
        Ok(count)
    }
}

#[derive(Clone, Debug)]
pub struct JsonlEventStore {
    path: PathBuf,
    signature_requirement: SignatureRequirement,
}
impl JsonlEventStore {
    pub fn new(path: impl Into<PathBuf>) -> MindResult<Self> {
        let path = path.into();
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)?;
            }
        }
        Ok(Self {
            path,
            signature_requirement: SignatureRequirement::Optional,
        })
    }
    #[must_use]
    pub fn with_signature_requirement(mut self, requirement: SignatureRequirement) -> Self {
        self.signature_requirement = requirement;
        self
    }
    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }
    fn read_all_records(&self) -> MindResult<Vec<EventRecord>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }
        let file = OpenOptions::new().read(true).open(&self.path)?;
        let reader = BufReader::new(file);
        let mut records = Vec::new();
        for line in reader.lines() {
            let line = line?;
            if !line.trim().is_empty() {
                records.push(serde_json::from_str::<EventRecord>(&line)?);
            }
        }
        Ok(records)
    }
}
impl AppendOnlyEventStore for JsonlEventStore {
    fn append(&mut self, commit: Commit) -> MindResult<EventRecord> {
        validate_commit_for_append(&commit, self.signature_requirement)?;
        let prior_records = self.records_for_mind(commit.mind_id)?;
        let sequence = prior_records.last().map_or(1, |r| r.sequence + 1);
        let previous_record_hash = prior_records.last().map(|r| r.record_hash.clone());
        let record = EventRecord::new(sequence, previous_record_hash, commit)?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{}", serde_json::to_string(&record)?)?;
        file.flush()?;
        file.sync_data()?;
        Ok(record)
    }
    fn records_for_mind(&self, mind_id: MindId) -> MindResult<Vec<EventRecord>> {
        Ok(self
            .read_all_records()?
            .into_iter()
            .filter(|r| r.mind_id == mind_id)
            .collect())
    }
    fn all_records(&self) -> MindResult<Vec<EventRecord>> {
        self.read_all_records()
    }
    fn signature_requirement(&self) -> SignatureRequirement {
        self.signature_requirement
    }
}

impl ReplicatedEventStore for JsonlEventStore {
    fn append_replicated_records(&mut self, records: Vec<EventRecord>) -> MindResult<usize> {
        if records.is_empty() {
            return Ok(0);
        }
        let mind_id = records[0].mind_id;
        if records.iter().any(|record| record.mind_id != mind_id) {
            return Err(MindError::DistributedAppendRejected {
                reason: "replicated records contain multiple mind ids".to_owned(),
            });
        }
        let prior_records = self.records_for_mind(mind_id)?;
        let expected_sequence = prior_records.last().map_or(1, |record| record.sequence + 1);
        let expected_previous_hash = prior_records
            .last()
            .map(|record| record.record_hash.clone());
        verify_record_tail_with_signatures(
            &records,
            expected_sequence,
            expected_previous_hash,
            self.signature_requirement,
        )?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        for record in &records {
            writeln!(file, "{}", serde_json::to_string(record)?)?;
        }
        file.flush()?;
        file.sync_data()?;
        Ok(records.len())
    }
}

pub fn validate_commit_for_append(
    commit: &Commit,
    requirement: SignatureRequirement,
) -> MindResult<()> {
    match (&commit.signature, requirement) {
        (None, SignatureRequirement::Required) => Err(MindError::CommitUnsigned {
            commit_id: commit.id,
        }),
        (None, SignatureRequirement::Optional) => Ok(()),
        (Some(_), _) => commit.verify_signature(),
    }
}

pub fn verify_record_chain(records: &[EventRecord]) -> MindResult<()> {
    verify_record_chain_with_signatures(records, SignatureRequirement::Optional)
}

pub fn verify_record_chain_with_signatures(
    records: &[EventRecord],
    signature_requirement: SignatureRequirement,
) -> MindResult<()> {
    verify_record_tail_with_signatures(records, 1, None, signature_requirement)
}

pub fn verify_record_tail_with_signatures(
    records: &[EventRecord],
    expected_start_sequence: u64,
    expected_previous_record_hash: Option<String>,
    signature_requirement: SignatureRequirement,
) -> MindResult<()> {
    let mut expected_previous_hash = expected_previous_record_hash;
    for (expected_sequence, record) in (expected_start_sequence..).zip(records.iter()) {
        if record.sequence != expected_sequence {
            return Err(MindError::EventSequenceGap {
                expected: expected_sequence,
                actual: record.sequence,
            });
        }
        if record.previous_record_hash.as_ref() != expected_previous_hash.as_ref() {
            return Err(MindError::EventChainBroken {
                sequence: record.sequence,
                expected: expected_previous_hash.clone(),
                actual: record.previous_record_hash.clone(),
            });
        }
        validate_commit_for_append(&record.commit, signature_requirement)?;
        let calculated = record.calculated_hash()?;
        if calculated != record.record_hash {
            return Err(MindError::EventRecordHashMismatch {
                sequence: record.sequence,
                expected: calculated,
                actual: record.record_hash.clone(),
            });
        }
        expected_previous_hash = Some(record.record_hash.clone());
    }
    Ok(())
}
