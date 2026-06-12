//! Purpose: audit event and telemetry export handlers for the Nested Mind API.
//! Governance scope: audit visibility and telemetry export endpoints without changing authorization, filtering, or response contracts.
//! Dependencies: API state, observability store, audit store, telemetry formatters, and authorization policy.
//! Invariants: audit read authorization, export filtering, audit writes, and response contracts remain behavior-preserving.

use super::*;

pub(super) async fn system_audit_events(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<AuditEvent>>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ReadObservability)?;
    Ok(Json(state.observability.read().await.audit_events()?))
}

pub(super) async fn system_telemetry_export(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<TelemetryExportQuery>,
) -> Result<Json<TelemetryExport>, ApiError> {
    let root_id = { state.root.read().await.id() };
    let principal = state.authn.authenticate(&headers)?;
    state
        .authz
        .require(principal.as_ref(), root_id, &MindAction::ExportTelemetry)?;
    let sink = state.observability.read().await;
    let traces = if query.include_traces {
        limit_tail(sink.trace_events()?, query.limit)
    } else {
        Vec::new()
    };
    let audits = if query.include_audits {
        limit_tail(sink.audit_events()?, query.limit)
    } else {
        Vec::new()
    };
    drop(sink);
    let export = TelemetryExporter::export(query.format, traces, audits)?;
    let _ = state.observability.write().await.record_audit(
        AuditEvent::new(
            AuditEventKind::TelemetryExported,
            "telemetry export generated",
        )
        .with_mind_id(root_id)
        .with_attribute("export_id", export.export_id.to_string())
        .with_attribute("format", format!("{:?}", export.format)),
    );
    Ok(Json(export))
}
