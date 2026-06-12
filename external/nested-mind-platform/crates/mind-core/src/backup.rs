use crate::{
    hash_serializable, verify_record_chain_with_signatures, AuditEvent, EventId, EventRecord,
    MindError, MindId, MindResult, ObservabilityEvent, SignatureRequirement, SnapshotRecord,
};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BackupRestoreMode {
    NewFilesOnly,
    ReplaceFiles,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BackupManifest {
    pub backup_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    pub created_at: OffsetDateTime,
    pub platform_schema_version: u64,
    pub event_count: usize,
    pub snapshot_count: usize,
    pub trace_count: usize,
    pub audit_count: usize,
    pub latest_event_sequence: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub latest_event_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub latest_snapshot_hash: Option<String>,
    pub backup_hash: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MindBackup {
    pub manifest: BackupManifest,
    #[serde(default)]
    pub event_records: Vec<EventRecord>,
    #[serde(default)]
    pub snapshots: Vec<SnapshotRecord>,
    #[serde(default)]
    pub trace_events: Vec<ObservabilityEvent>,
    #[serde(default)]
    pub audit_events: Vec<AuditEvent>,
}

impl MindBackup {
    pub fn capture(
        mind_id: Option<MindId>,
        event_records: Vec<EventRecord>,
        snapshots: Vec<SnapshotRecord>,
        trace_events: Vec<ObservabilityEvent>,
        audit_events: Vec<AuditEvent>,
        platform_schema_version: u64,
    ) -> MindResult<Self> {
        if let Some(expected) = mind_id {
            if let Some(record) = event_records
                .iter()
                .find(|record| record.mind_id != expected)
            {
                return Err(MindError::BackupMindMismatch {
                    expected,
                    actual: record.mind_id,
                });
            }
            if let Some(snapshot) = snapshots
                .iter()
                .find(|snapshot| snapshot.mind_id != expected)
            {
                return Err(MindError::BackupMindMismatch {
                    expected,
                    actual: snapshot.mind_id,
                });
            }
        }
        for snapshot in &snapshots {
            snapshot.verify()?;
        }
        let latest_event_sequence = event_records.last().map(|record| record.sequence);
        let latest_event_hash = event_records
            .last()
            .map(|record| record.record_hash.clone());
        let latest_snapshot_hash = snapshots
            .last()
            .map(|snapshot| snapshot.snapshot_hash.clone());
        let manifest = BackupManifest {
            backup_id: EventId::new(),
            mind_id,
            created_at: OffsetDateTime::now_utc(),
            platform_schema_version,
            event_count: event_records.len(),
            snapshot_count: snapshots.len(),
            trace_count: trace_events.len(),
            audit_count: audit_events.len(),
            latest_event_sequence,
            latest_event_hash,
            latest_snapshot_hash,
            backup_hash: String::new(),
        };
        let mut backup = Self {
            manifest,
            event_records,
            snapshots,
            trace_events,
            audit_events,
        };
        backup.manifest.backup_hash = backup.calculated_hash()?;
        Ok(backup)
    }

    pub fn calculated_hash(&self) -> MindResult<String> {
        let body = BackupHashBody {
            manifest: BackupManifestHashBody {
                backup_id: self.manifest.backup_id,
                mind_id: self.manifest.mind_id,
                created_at: self.manifest.created_at,
                platform_schema_version: self.manifest.platform_schema_version,
                event_count: self.manifest.event_count,
                snapshot_count: self.manifest.snapshot_count,
                trace_count: self.manifest.trace_count,
                audit_count: self.manifest.audit_count,
                latest_event_sequence: self.manifest.latest_event_sequence,
                latest_event_hash: &self.manifest.latest_event_hash,
                latest_snapshot_hash: &self.manifest.latest_snapshot_hash,
            },
            event_records: &self.event_records,
            snapshots: &self.snapshots,
            trace_events: &self.trace_events,
            audit_events: &self.audit_events,
        };
        hash_serializable(&body)
    }

    pub fn verify(
        &self,
        signature_requirement: SignatureRequirement,
    ) -> MindResult<BackupVerificationReport> {
        let calculated = self.calculated_hash()?;
        let hash_valid = calculated == self.manifest.backup_hash;
        if !hash_valid {
            return Err(MindError::BackupHashMismatch {
                expected: calculated,
                actual: self.manifest.backup_hash.clone(),
            });
        }
        if self.manifest.event_count != self.event_records.len()
            || self.manifest.snapshot_count != self.snapshots.len()
            || self.manifest.trace_count != self.trace_events.len()
            || self.manifest.audit_count != self.audit_events.len()
        {
            return Err(MindError::BackupManifestMismatch);
        }
        if let Some(mind_id) = self.manifest.mind_id {
            if let Some(record) = self
                .event_records
                .iter()
                .find(|record| record.mind_id != mind_id)
            {
                return Err(MindError::BackupMindMismatch {
                    expected: mind_id,
                    actual: record.mind_id,
                });
            }
            if let Some(snapshot) = self
                .snapshots
                .iter()
                .find(|snapshot| snapshot.mind_id != mind_id)
            {
                return Err(MindError::BackupMindMismatch {
                    expected: mind_id,
                    actual: snapshot.mind_id,
                });
            }
        }
        verify_record_chain_with_signatures(&self.event_records, signature_requirement)?;
        for snapshot in &self.snapshots {
            snapshot.verify()?;
        }
        Ok(BackupVerificationReport {
            backup_id: self.manifest.backup_id,
            mind_id: self.manifest.mind_id,
            valid: true,
            event_count: self.event_records.len(),
            snapshot_count: self.snapshots.len(),
            trace_count: self.trace_events.len(),
            audit_count: self.audit_events.len(),
            latest_event_sequence: self.event_records.last().map(|record| record.sequence),
            latest_event_hash: self
                .event_records
                .last()
                .map(|record| record.record_hash.clone()),
            backup_hash: self.manifest.backup_hash.clone(),
        })
    }
}

#[derive(Serialize)]
struct BackupHashBody<'a> {
    manifest: BackupManifestHashBody<'a>,
    event_records: &'a [EventRecord],
    snapshots: &'a [SnapshotRecord],
    trace_events: &'a [ObservabilityEvent],
    audit_events: &'a [AuditEvent],
}

#[derive(Serialize)]
struct BackupManifestHashBody<'a> {
    backup_id: EventId,
    mind_id: Option<MindId>,
    created_at: OffsetDateTime,
    platform_schema_version: u64,
    event_count: usize,
    snapshot_count: usize,
    trace_count: usize,
    audit_count: usize,
    latest_event_sequence: Option<u64>,
    latest_event_hash: &'a Option<String>,
    latest_snapshot_hash: &'a Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BackupVerificationReport {
    pub backup_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    pub valid: bool,
    pub event_count: usize,
    pub snapshot_count: usize,
    pub trace_count: usize,
    pub audit_count: usize,
    pub latest_event_sequence: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub latest_event_hash: Option<String>,
    pub backup_hash: String,
}

#[derive(Clone, Debug)]
pub struct JsonBackupStore {
    path: PathBuf,
}

impl JsonBackupStore {
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

    pub fn save(&self, backup: &MindBackup) -> MindResult<()> {
        let mut file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&self.path)?;
        file.write_all(serde_json::to_string_pretty(backup)?.as_bytes())?;
        file.write_all(b"\n")?;
        file.flush()?;
        file.sync_data()?;
        Ok(())
    }

    pub fn load(&self) -> MindResult<MindBackup> {
        let file = OpenOptions::new().read(true).open(&self.path)?;
        Ok(serde_json::from_reader::<_, MindBackup>(file)?)
    }

    pub fn restore_to_jsonl<P1, P2, P3>(
        &self,
        event_log: P1,
        snapshot_log: P2,
        observability_log: Option<P3>,
        signature_requirement: SignatureRequirement,
        mode: BackupRestoreMode,
    ) -> MindResult<BackupVerificationReport>
    where
        P1: AsRef<Path>,
        P2: AsRef<Path>,
        P3: AsRef<Path>,
    {
        let backup = self.load()?;
        let report = backup.verify(signature_requirement)?;
        write_jsonl_file(event_log.as_ref(), &backup.event_records, &mode)?;
        write_jsonl_file(snapshot_log.as_ref(), &backup.snapshots, &mode)?;
        if let Some(path) = observability_log {
            let mut records = Vec::new();
            records.extend(
                backup
                    .trace_events
                    .iter()
                    .map(|event| RestoredObservabilityRecord::Trace(event.clone())),
            );
            records.extend(
                backup
                    .audit_events
                    .iter()
                    .map(|event| RestoredObservabilityRecord::Audit(event.clone())),
            );
            write_jsonl_file(path.as_ref(), &records, &mode)?;
        }
        Ok(report)
    }
}

#[derive(Serialize)]
#[serde(tag = "record_type", content = "record", rename_all = "snake_case")]
enum RestoredObservabilityRecord {
    Trace(ObservabilityEvent),
    Audit(AuditEvent),
}

fn write_jsonl_file<T: Serialize>(
    path: &Path,
    records: &[T],
    mode: &BackupRestoreMode,
) -> MindResult<()> {
    if matches!(mode, &BackupRestoreMode::NewFilesOnly) && path.exists() {
        return Err(MindError::BackupRestoreTargetExists(
            path.display().to_string(),
        ));
    }
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    let temporary_path = path.with_extension("restore.tmp");
    {
        let mut file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&temporary_path)?;
        for record in records {
            writeln!(file, "{}", serde_json::to_string(record)?)?;
        }
        file.flush()?;
        file.sync_data()?;
    }
    fs::rename(temporary_path, path)?;
    Ok(())
}

pub fn read_backup_manifests_jsonl(path: impl AsRef<Path>) -> MindResult<Vec<BackupManifest>> {
    let path = path.as_ref();
    if !path.exists() {
        return Ok(Vec::new());
    }
    let file = OpenOptions::new().read(true).open(path)?;
    let reader = BufReader::new(file);
    let mut manifests = Vec::new();
    for line in reader.lines() {
        let line = line?;
        if !line.trim().is_empty() {
            manifests.push(serde_json::from_str::<BackupManifest>(&line)?);
        }
    }
    Ok(manifests)
}
