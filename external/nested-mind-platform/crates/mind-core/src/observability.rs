use crate::{EventId, MindError, MindId, MindResult};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
};
use time::OffsetDateTime;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TraceContext {
    pub trace_id: EventId,
    pub span_id: EventId,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent_span_id: Option<EventId>,
    pub operation: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actor: Option<String>,
    pub started_at: OffsetDateTime,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl TraceContext {
    #[must_use]
    pub fn root(operation: impl Into<String>) -> Self {
        let trace_id = EventId::new();
        Self {
            trace_id,
            span_id: EventId::new(),
            parent_span_id: None,
            operation: operation.into(),
            mind_id: None,
            actor: None,
            started_at: OffsetDateTime::now_utc(),
            attributes: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn child(&self, operation: impl Into<String>) -> Self {
        Self {
            trace_id: self.trace_id,
            span_id: EventId::new(),
            parent_span_id: Some(self.span_id),
            operation: operation.into(),
            mind_id: self.mind_id,
            actor: self.actor.clone(),
            started_at: OffsetDateTime::now_utc(),
            attributes: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn with_mind_id(mut self, mind_id: MindId) -> Self {
        self.mind_id = Some(mind_id);
        self
    }

    #[must_use]
    pub fn with_actor(mut self, actor: impl Into<String>) -> Self {
        self.actor = Some(actor.into());
        self
    }

    #[must_use]
    pub fn with_attribute(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.attributes.insert(key.into(), value.into());
        self
    }

    #[must_use]
    pub fn finish(self, outcome: TraceOutcome) -> ObservabilityEvent {
        let finished_at = OffsetDateTime::now_utc();
        let duration = finished_at - self.started_at;
        let duration_ms = duration.whole_milliseconds().max(0) as u64;
        ObservabilityEvent {
            trace: self,
            finished_at,
            duration_ms,
            outcome,
        }
    }

    #[must_use]
    pub fn finish_success(self) -> ObservabilityEvent {
        self.finish(TraceOutcome::Succeeded)
    }

    #[must_use]
    pub fn finish_failure(self, error: impl Into<String>) -> ObservabilityEvent {
        self.finish(TraceOutcome::Failed {
            error: error.into(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "outcome", rename_all = "snake_case")]
pub enum TraceOutcome {
    Succeeded,
    Failed { error: String },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObservabilityEvent {
    pub trace: TraceContext,
    pub finished_at: OffsetDateTime,
    pub duration_ms: u64,
    pub outcome: TraceOutcome,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AuditEventKind {
    Authenticated,
    Authorized,
    Rejected,
    MutationCommitted,
    ChildAttached,
    LawbookMigrated,
    SnapshotCreated,
    SnapshotCompacted,
    SchemaMigrated,
    ReplayAudited,
    TelemetryExported,
    BackupCreated,
    BackupVerified,
    BackupRestored,
    ObjectBackupCreated,
    ObjectBackupVerified,
    IdentityMapped,
    KeyCustodyChecked,
    DistributedPlanChecked,
    RequestRejected,
    HealthChecked,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuditEvent {
    pub event_id: EventId,
    pub at: OffsetDateTime,
    pub kind: AuditEventKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<EventId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mind_id: Option<MindId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actor: Option<String>,
    pub message: String,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl AuditEvent {
    #[must_use]
    pub fn new(kind: AuditEventKind, message: impl Into<String>) -> Self {
        Self {
            event_id: EventId::new(),
            at: OffsetDateTime::now_utc(),
            kind,
            trace_id: None,
            mind_id: None,
            actor: None,
            message: message.into(),
            attributes: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn with_trace_id(mut self, trace_id: EventId) -> Self {
        self.trace_id = Some(trace_id);
        self
    }

    #[must_use]
    pub fn with_mind_id(mut self, mind_id: MindId) -> Self {
        self.mind_id = Some(mind_id);
        self
    }

    #[must_use]
    pub fn with_actor(mut self, actor: impl Into<String>) -> Self {
        self.actor = Some(actor.into());
        self
    }

    #[must_use]
    pub fn with_attribute(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.attributes.insert(key.into(), value.into());
        self
    }
}

pub trait ObservabilitySink {
    fn record_trace(&mut self, event: ObservabilityEvent) -> MindResult<()>;
    fn record_audit(&mut self, event: AuditEvent) -> MindResult<()>;
    fn trace_events(&self) -> MindResult<Vec<ObservabilityEvent>> {
        Ok(Vec::new())
    }
    fn audit_events(&self) -> MindResult<Vec<AuditEvent>> {
        Ok(Vec::new())
    }
}

#[derive(Clone, Debug, Default)]
pub struct NullObservabilitySink;
impl ObservabilitySink for NullObservabilitySink {
    fn record_trace(&mut self, _event: ObservabilityEvent) -> MindResult<()> {
        Ok(())
    }
    fn record_audit(&mut self, _event: AuditEvent) -> MindResult<()> {
        Ok(())
    }
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryObservabilitySink {
    traces: Vec<ObservabilityEvent>,
    audits: Vec<AuditEvent>,
}

impl InMemoryObservabilitySink {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }
}

impl ObservabilitySink for InMemoryObservabilitySink {
    fn record_trace(&mut self, event: ObservabilityEvent) -> MindResult<()> {
        self.traces.push(event);
        Ok(())
    }
    fn record_audit(&mut self, event: AuditEvent) -> MindResult<()> {
        self.audits.push(event);
        Ok(())
    }
    fn trace_events(&self) -> MindResult<Vec<ObservabilityEvent>> {
        Ok(self.traces.clone())
    }
    fn audit_events(&self) -> MindResult<Vec<AuditEvent>> {
        Ok(self.audits.clone())
    }
}

#[derive(Clone, Debug)]
pub struct JsonlObservabilitySink {
    path: PathBuf,
}

impl JsonlObservabilitySink {
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

    fn append(&self, record: PersistedObservabilityRecord) -> MindResult<()> {
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{}", serde_json::to_string(&record)?)?;
        file.flush()?;
        file.sync_data()?;
        Ok(())
    }

    fn read_records(&self) -> MindResult<Vec<PersistedObservabilityRecord>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }
        let file = OpenOptions::new().read(true).open(&self.path)?;
        let reader = BufReader::new(file);
        let mut records = Vec::new();
        for line in reader.lines() {
            let line = line?;
            if !line.trim().is_empty() {
                records.push(serde_json::from_str::<PersistedObservabilityRecord>(&line)?);
            }
        }
        Ok(records)
    }
}

impl ObservabilitySink for JsonlObservabilitySink {
    fn record_trace(&mut self, event: ObservabilityEvent) -> MindResult<()> {
        self.append(PersistedObservabilityRecord::Trace(event))
    }
    fn record_audit(&mut self, event: AuditEvent) -> MindResult<()> {
        self.append(PersistedObservabilityRecord::Audit(event))
    }
    fn trace_events(&self) -> MindResult<Vec<ObservabilityEvent>> {
        Ok(self
            .read_records()?
            .into_iter()
            .filter_map(|record| match record {
                PersistedObservabilityRecord::Trace(event) => Some(event),
                PersistedObservabilityRecord::Audit(_) => None,
            })
            .collect())
    }
    fn audit_events(&self) -> MindResult<Vec<AuditEvent>> {
        Ok(self
            .read_records()?
            .into_iter()
            .filter_map(|record| match record {
                PersistedObservabilityRecord::Audit(event) => Some(event),
                PersistedObservabilityRecord::Trace(_) => None,
            })
            .collect())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "record_type", content = "record", rename_all = "snake_case")]
enum PersistedObservabilityRecord {
    Trace(ObservabilityEvent),
    Audit(AuditEvent),
}

#[allow(dead_code)]
pub fn observability_error(error: impl Into<String>) -> MindError {
    MindError::Observability(error.into())
}
