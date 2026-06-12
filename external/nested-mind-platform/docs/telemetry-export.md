# Telemetry Export

The runtime records governed audit events and can export trace/audit data through a protected endpoint.

```text
GET /system/observability/export?format=internal_json
GET /system/observability/export?format=otlp_json
```

Required permission:

```text
ExportTelemetry
```

## Formats

`internal_json` preserves the platform-native event structure:

```text
TelemetryExport {
  export_id,
  generated_at,
  trace_count,
  audit_count,
  payload_hash,
  payload: { traces, audit_events }
}
```

`otlp_json` emits an OTLP-shaped JSON document with `resourceSpans` and `resourceLogs`. This is an integration bridge, not yet a direct OTLP/gRPC exporter.

## Persistence

Observability can be kept in memory, JSONL, or SQLite.

```bash
MIND_OBSERVABILITY_LOG=./data/observability.jsonl
MIND_OBSERVABILITY_DB=./data/mind-events.sqlite
MIND_OBSERVABILITY_USE_EVENT_DB=true
```

If `MIND_OBSERVABILITY_USE_EVENT_DB=true`, the API opens the same SQLite file used by the event store and writes observability rows into the `observability_events` table.
