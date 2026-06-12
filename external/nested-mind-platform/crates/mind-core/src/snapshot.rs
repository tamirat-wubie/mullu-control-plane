use crate::{
    hash_serializable, hash_state, Commit, EventId, EventRecord, Identity, Lawbook, Mind,
    MindError, MindId, MindResult, SymbolState,
};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MindSnapshot {
    pub identity: Identity,
    pub lawbook: Lawbook,
    pub state: SymbolState,
    #[serde(default)]
    pub children: Vec<MindSnapshot>,
    #[serde(default)]
    pub history: Vec<Commit>,
}

impl MindSnapshot {
    #[must_use]
    pub fn capture(mind: &Mind) -> Self {
        Self {
            identity: mind.identity().clone(),
            lawbook: mind.lawbook().clone(),
            state: mind.state().clone(),
            children: mind.children().values().map(Self::capture).collect(),
            history: mind.history().to_vec(),
        }
    }

    pub fn restore(&self) -> MindResult<Mind> {
        let children = self
            .children
            .iter()
            .map(MindSnapshot::restore)
            .collect::<MindResult<Vec<_>>>()?;
        Mind::from_restored_parts(
            self.identity.clone(),
            self.lawbook.clone(),
            self.state.clone(),
            children,
            self.history.clone(),
        )
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SnapshotRecord {
    pub snapshot_id: EventId,
    pub mind_id: MindId,
    pub captured_at: OffsetDateTime,
    pub after_sequence: u64,
    pub after_record_hash: Option<String>,
    pub latest_commit_id: Option<EventId>,
    pub commit_count: usize,
    pub child_count: usize,
    pub state_hash: String,
    pub lawbook_hash: String,
    pub snapshot_hash: String,
    pub snapshot: MindSnapshot,
}

impl SnapshotRecord {
    pub fn capture(mind: &Mind, latest_record: Option<&EventRecord>) -> MindResult<Self> {
        let snapshot = MindSnapshot::capture(mind);
        let state_hash = hash_state(mind.state())?;
        let lawbook_hash = mind.lawbook().hash()?;
        let snapshot_id = EventId::new();
        let after_sequence =
            latest_record.map_or(mind.history().len() as u64, |record| record.sequence);
        let after_record_hash = latest_record.map(|record| record.record_hash.clone());
        let mut record = Self {
            snapshot_id,
            mind_id: mind.id(),
            captured_at: OffsetDateTime::now_utc(),
            after_sequence,
            after_record_hash,
            latest_commit_id: mind.latest_commit_id(),
            commit_count: mind.history().len(),
            child_count: mind.children().len(),
            state_hash,
            lawbook_hash,
            snapshot_hash: String::new(),
            snapshot,
        };
        record.snapshot_hash = record.calculated_hash()?;
        Ok(record)
    }

    pub fn calculated_hash(&self) -> MindResult<String> {
        let body = SnapshotRecordBody {
            snapshot_id: self.snapshot_id,
            mind_id: self.mind_id,
            captured_at: self.captured_at,
            after_sequence: self.after_sequence,
            after_record_hash: &self.after_record_hash,
            latest_commit_id: self.latest_commit_id,
            commit_count: self.commit_count,
            child_count: self.child_count,
            state_hash: &self.state_hash,
            lawbook_hash: &self.lawbook_hash,
            snapshot: &self.snapshot,
        };
        hash_serializable(&body)
    }

    pub fn verify(&self) -> MindResult<()> {
        let calculated = self.calculated_hash()?;
        if calculated != self.snapshot_hash {
            return Err(MindError::SnapshotHashMismatch {
                expected: calculated,
                actual: self.snapshot_hash.clone(),
            });
        }
        let state_hash = hash_state(&self.snapshot.state)?;
        if state_hash != self.state_hash {
            return Err(MindError::SnapshotStateHashMismatch {
                expected: self.state_hash.clone(),
                actual: state_hash,
            });
        }
        let lawbook_hash = self.snapshot.lawbook.hash()?;
        if lawbook_hash != self.lawbook_hash {
            return Err(MindError::SnapshotLawbookHashMismatch {
                expected: self.lawbook_hash.clone(),
                actual: lawbook_hash,
            });
        }
        Ok(())
    }

    pub fn restore_mind(&self) -> MindResult<Mind> {
        self.verify()?;
        self.snapshot.restore()
    }
}

#[derive(Serialize)]
struct SnapshotRecordBody<'a> {
    snapshot_id: EventId,
    mind_id: MindId,
    captured_at: OffsetDateTime,
    after_sequence: u64,
    after_record_hash: &'a Option<String>,
    latest_commit_id: Option<EventId>,
    commit_count: usize,
    child_count: usize,
    state_hash: &'a str,
    lawbook_hash: &'a str,
    snapshot: &'a MindSnapshot,
}

pub trait SnapshotStore {
    fn save_snapshot(&mut self, snapshot: SnapshotRecord) -> MindResult<SnapshotRecord>;
    fn latest_snapshot_for_mind(&self, mind_id: MindId) -> MindResult<Option<SnapshotRecord>>;
    fn snapshots_for_mind(&self, mind_id: MindId) -> MindResult<Vec<SnapshotRecord>>;
}

#[derive(Clone, Debug, Default)]
pub struct InMemorySnapshotStore {
    pub(crate) snapshots: Vec<SnapshotRecord>,
}
impl InMemorySnapshotStore {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }
}
impl SnapshotStore for InMemorySnapshotStore {
    fn save_snapshot(&mut self, snapshot: SnapshotRecord) -> MindResult<SnapshotRecord> {
        snapshot.verify()?;
        self.snapshots.push(snapshot.clone());
        Ok(snapshot)
    }
    fn latest_snapshot_for_mind(&self, mind_id: MindId) -> MindResult<Option<SnapshotRecord>> {
        Ok(self
            .snapshots
            .iter()
            .rev()
            .find(|snapshot| snapshot.mind_id == mind_id)
            .cloned())
    }
    fn snapshots_for_mind(&self, mind_id: MindId) -> MindResult<Vec<SnapshotRecord>> {
        Ok(self
            .snapshots
            .iter()
            .filter(|snapshot| snapshot.mind_id == mind_id)
            .cloned()
            .collect())
    }
}

#[derive(Clone, Debug)]
pub struct JsonlSnapshotStore {
    path: PathBuf,
}
impl JsonlSnapshotStore {
    pub fn new(path: impl Into<PathBuf>) -> MindResult<Self> {
        let path = path.into();
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)?;
            }
        }
        Ok(Self { path })
    }
    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }
    pub(crate) fn read_all_snapshots(&self) -> MindResult<Vec<SnapshotRecord>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }
        let file = OpenOptions::new().read(true).open(&self.path)?;
        let reader = BufReader::new(file);
        let mut snapshots = Vec::new();
        for line in reader.lines() {
            let line = line?;
            if !line.trim().is_empty() {
                snapshots.push(serde_json::from_str::<SnapshotRecord>(&line)?);
            }
        }
        Ok(snapshots)
    }

    pub(crate) fn rewrite_all_snapshots(&self, snapshots: &[SnapshotRecord]) -> MindResult<()> {
        let temporary_path = self.path.with_extension("jsonl.tmp");
        {
            let mut file = OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(true)
                .open(&temporary_path)?;
            for snapshot in snapshots {
                snapshot.verify()?;
                writeln!(file, "{}", serde_json::to_string(snapshot)?)?;
            }
            file.flush()?;
            file.sync_data()?;
        }
        fs::rename(temporary_path, &self.path)?;
        Ok(())
    }
}
impl SnapshotStore for JsonlSnapshotStore {
    fn save_snapshot(&mut self, snapshot: SnapshotRecord) -> MindResult<SnapshotRecord> {
        snapshot.verify()?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{}", serde_json::to_string(&snapshot)?)?;
        file.flush()?;
        file.sync_data()?;
        Ok(snapshot)
    }
    fn latest_snapshot_for_mind(&self, mind_id: MindId) -> MindResult<Option<SnapshotRecord>> {
        Ok(self
            .read_all_snapshots()?
            .into_iter()
            .rev()
            .find(|snapshot| snapshot.mind_id == mind_id))
    }
    fn snapshots_for_mind(&self, mind_id: MindId) -> MindResult<Vec<SnapshotRecord>> {
        Ok(self
            .read_all_snapshots()?
            .into_iter()
            .filter(|snapshot| snapshot.mind_id == mind_id)
            .collect())
    }
}
