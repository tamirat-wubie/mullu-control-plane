# ADR 0005: Request Safety, Telemetry Export, Backup, and Deployment

## Decision

Add a runtime maintenance layer around the symbolic kernel:

```text
request safety
  + telemetry export
  + backup verification
  + deployment manifests
```

## Rationale

The kernel should remain deterministic and side-effect free. Operational features belong at the runtime boundary:

```text
Γ handles exposure
H handles causal evidence
runtime handles transport safety, persistence, and recovery
```

## Consequences

Constructive:

```text
+ API rejects oversized requests before mutation
+ API rate limits by principal/path
+ telemetry can be exported without changing kernel state
+ backup objects are hash-verifiable
+ restore writes new files instead of mutating live state
+ deployment templates express single-writer SQLite limits
```

Fracture:

```text
- rate limit is not distributed
- OTLP export is JSON-shaped, not direct exporter transport
- live restore is intentionally absent
- Kubernetes deployment is single-replica until storage model changes
```
