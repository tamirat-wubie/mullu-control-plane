# Observability

Observability separates platform telemetry from symbolic state.

Objects:

```text
TraceContext
ObservabilityEvent
AuditEvent
AuditEventKind
ObservabilitySink
```

Supported sinks:

```text
+ NullObservabilitySink
+ InMemoryObservabilitySink
+ JsonlObservabilitySink
+ SQLite-backed SqliteEventStore observability sink
```

Runtime configuration:

```bash
export MIND_OBSERVABILITY_LOG="./data/observability.jsonl"
# or disable:
export MIND_OBSERVABILITY=off
```

API:

```text
GET /system/observability/audit-events
GET /system/observability/export?format=internal_json
GET /system/observability/export?format=otlp_json
```

CLI:

```bash
cargo run -p mind-cli -- audit-events-jsonl ./data/observability.jsonl
cargo run -p mind-cli -- telemetry-jsonl ./data/observability.jsonl otlp_json
```

Governance rule: observability records must not mutate Σ. They record runtime actions around Σ, H, Λ, and Γ.

## Runtime HTTP tracing

```bash
export MIND_LOG_LEVEL="mind_api=info,tower_http=info"
export MIND_TRACE_JSON=false
```

The API attaches request tracing at the HTTP router boundary. Symbolic state evolution remains controlled by the kernel and audit records stay outside Σ.
