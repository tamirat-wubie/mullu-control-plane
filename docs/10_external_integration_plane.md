# External Integration Plane (MXI)

Scope: all Mullu Platform modules that connect to systems outside the platform boundary.

The External Integration Plane governs connections to APIs, SaaS services, databases, browsers, LLMs, and any other system outside the platform trust boundary. Every external interaction passes through this plane. No module may contact an external system directly.

## Purpose

Manage the lifecycle of external connectors: registration, invocation, health tracking, and retirement. Ensure every external interaction is typed, auditable, and bounded by declared credential scope.

## Owned artifacts

- **Connector descriptors**: declare a connector's identity, provider, effect class, trust class, and credential scope. Schema: `connector_descriptor.schema.json`.
- **Connector invocation results**: record every invocation outcome with status, timing, and response digest. Schema: `connector_result.schema.json`.
- **Connector health records**: track per-connector availability, latency percentiles, and error rates over time.

## Trust and effect classification

Every connector MUST declare exactly one `EffectClass` and one `TrustClass` at registration time.

### EffectClass values

| Value | Meaning |
|---|---|
| `internal_pure` | No external side effects. Deterministic transformation only. |
| `external_read` | Reads from an external system. No mutation. |
| `external_write` | Mutates state in an external system. |
| `human_mediated` | Requires human approval or interaction to complete. |
| `privileged` | Operates with elevated permissions in the external system. |

### TrustClass values

| Value | Meaning |
|---|---|
| `trusted_internal` | Platform-internal service. Responses treated as structurally valid. |
| `bounded_external` | Known external provider with contractual SLA. Responses validated before use. |
| `untrusted_external` | Unknown or unverified external source. Responses treated as adversarial input. |

Rules:
- A connector with `effect_class: external_write` or `privileged` MUST have policy approval before each invocation.
- A connector with `trust_class: untrusted_external` MUST have its responses validated against an expected schema before any downstream use.
- Trust class MUST NOT be promoted at runtime. A connector registered as `bounded_external` stays `bounded_external`.

## Verification expectations

- Every connector invocation MUST produce a typed `ConnectorResult` regardless of outcome.
- External responses are untrusted until validated by the consuming plane.
- Response validation MUST check structural conformance and value-range plausibility.
- A missing or malformed response MUST produce a `ConnectorResult` with `status: failed` and a diagnostic `error_code`.

## Policy hooks

- **Credential scope enforcement**: every invocation MUST verify that the requested operation falls within the connector's declared `credential_scope_id`. Scope violations are rejected before the call leaves the platform.
- **Rate and cost limits**: connectors MAY declare rate limits and per-invocation cost estimates. The plane enforces these limits and rejects invocations that would exceed them.
- **Provider reliability history**: the plane tracks per-connector success rates. Governance MAY define minimum reliability thresholds below which a connector is automatically disabled.

## Failure modes

| Mode | Meaning | Recoverability |
|---|---|---|
| `timeout` | External system did not respond within the declared deadline. | Retryable. |
| `auth_failure` | Credentials rejected or expired. | Requires credential refresh. |
| `rate_limit` | External system returned a rate-limit signal. | Retryable after backoff. |
| `malformed_response` | Response does not conform to expected structure. | Not retryable without provider fix. |
| `provider_unavailable` | External system is down or unreachable. | Retryable after backoff or failover. |

Every failure MUST be recorded in the connector invocation result and linked to the originating trace.

## Prohibitions

- MUST NOT use credentials outside their declared scope.
- MUST NOT cache external responses as trusted world state. External data enters the World State Plane only through re-observation.
- MUST NOT expose internal identifiers (execution IDs, trace IDs, tenant IDs) to external systems.
- MUST NOT retry `external_write` invocations automatically. Write retries require explicit policy approval.
- MUST NOT invoke a disabled connector.

## Dependencies

- Governance Plane: credential policy, rate-limit policy, reliability thresholds.
- Capability Plane: integration capabilities declared per connector.
- Verification Plane: response validation rules.
