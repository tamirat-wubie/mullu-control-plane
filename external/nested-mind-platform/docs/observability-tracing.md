# Observability and Tracing

v6 separates three operational signals:

```text
HTTP tracing            request/response visibility at the API boundary
Audit-event sink        governed platform actions such as mutations, snapshots, compaction, lawbook migration, backup, and export
Telemetry export        protected internal JSON or OTLP-shaped JSON payload
```

Configuration:

`MIND_TRACE_LEVEL` is still accepted as a compatibility alias when `MIND_LOG_LEVEL` is unset.


```bash
export MIND_LOG_LEVEL="mind_api=info,tower_http=info"
export MIND_TRACE_JSON=true
export MIND_OBSERVABILITY_LOG="./data/observability.jsonl"
export MIND_OBSERVABILITY_USE_EVENT_DB=true
```

Rules:

```text
- do not log bearer tokens
- do not log signing seeds
- do not log raw SymbolState cells
- do log commit ids, snapshot ids, action kinds, status, and timing metadata
```

The API owns tracing. The kernel owns deterministic state evolution and remains free of runtime logging side effects.
