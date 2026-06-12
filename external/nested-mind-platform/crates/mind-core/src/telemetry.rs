use crate::{hash_serializable, AuditEvent, EventId, MindResult, ObservabilityEvent, TraceOutcome};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use time::OffsetDateTime;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[derive(Default)]
pub enum TelemetryExportFormat {
    #[default]
    InternalJson,
    OtlpJson,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TelemetryExport {
    pub export_id: EventId,
    pub generated_at: OffsetDateTime,
    pub format: TelemetryExportFormat,
    pub trace_count: usize,
    pub audit_count: usize,
    pub payload_hash: String,
    pub payload: Value,
}

impl TelemetryExport {
    pub fn new(
        format: TelemetryExportFormat,
        traces: Vec<ObservabilityEvent>,
        audits: Vec<AuditEvent>,
    ) -> MindResult<Self> {
        let payload = match format {
            TelemetryExportFormat::InternalJson => json!({
                "schema": "nested_mind.telemetry.v1",
                "traces": traces,
                "audit_events": audits,
            }),
            TelemetryExportFormat::OtlpJson => otlp_shaped_payload(&traces, &audits),
        };
        let payload_hash = hash_serializable(&payload)?;
        Ok(Self {
            export_id: EventId::new(),
            generated_at: OffsetDateTime::now_utc(),
            format,
            trace_count: traces.len(),
            audit_count: audits.len(),
            payload_hash,
            payload,
        })
    }
}

#[derive(Clone, Debug, Default)]
pub struct TelemetryExporter;

impl TelemetryExporter {
    pub fn export(
        format: TelemetryExportFormat,
        traces: Vec<ObservabilityEvent>,
        audits: Vec<AuditEvent>,
    ) -> MindResult<TelemetryExport> {
        TelemetryExport::new(format, traces, audits)
    }
}

fn otlp_shaped_payload(traces: &[ObservabilityEvent], audits: &[AuditEvent]) -> Value {
    let spans: Vec<Value> = traces.iter().map(|event| {
        let status = match &event.outcome {
            TraceOutcome::Succeeded => json!({"code": "STATUS_CODE_OK"}),
            TraceOutcome::Failed { error } => json!({"code": "STATUS_CODE_ERROR", "message": error}),
        };
        json!({
            "traceId": event.trace.trace_id.to_string(),
            "spanId": event.trace.span_id.to_string(),
            "parentSpanId": event.trace.parent_span_id.map(|id| id.to_string()),
            "name": &event.trace.operation,
            "startTimeUnixNano": event.trace.started_at.unix_timestamp_nanos().to_string(),
            "endTimeUnixNano": event.finished_at.unix_timestamp_nanos().to_string(),
            "attributes": event.trace.attributes.iter().map(|(key, value)| json!({"key": key, "value": {"stringValue": value}})).collect::<Vec<_>>(),
            "status": status,
        })
    }).collect();

    let logs: Vec<Value> = audits.iter().map(|event| {
        json!({
            "timeUnixNano": event.at.unix_timestamp_nanos().to_string(),
            "name": format!("{:?}", &event.kind),
            "body": {"stringValue": &event.message},
            "attributes": event.attributes.iter().map(|(key, value)| json!({"key": key, "value": {"stringValue": value}})).chain([
                json!({"key": "event_id", "value": {"stringValue": event.event_id.to_string()}}),
                json!({"key": "actor", "value": {"stringValue": event.actor.clone().unwrap_or_default()}}),
                json!({"key": "mind_id", "value": {"stringValue": event.mind_id.map(|id| id.to_string()).unwrap_or_default()}}),
            ]).collect::<Vec<_>>(),
        })
    }).collect();

    json!({
        "resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "nested-mind-platform"}}]},
            "scopeSpans": [{"scope": {"name": "mind-api"}, "spans": spans}]
        }],
        "resourceLogs": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "nested-mind-platform"}}]},
            "scopeLogs": [{"scope": {"name": "mind-api"}, "logRecords": logs}]
        }]
    })
}
