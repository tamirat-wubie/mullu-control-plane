# Model Orchestration Plane (MMOI)

Scope: all Mullu Platform modules that invoke LLMs or other inference models.

The Model Orchestration Plane selects, invokes, and governs model providers. Model outputs are bounded external inferences. They are never trusted directly and MUST pass through admission or validation before influencing planning or world state.

## Purpose

Provide governed, cost-controlled, auditable model invocation. Ensure every model call has a prompt policy check, a typed result, and a cost record.

## Owned artifacts

- **Model invocation records**: record every model call with model ID, prompt hash, token counts, and cost estimate. Schema: `model_invocation.schema.json`.
- **Model response records**: record every model response with status, output digest, token counts, actual cost, and validation status. Schema: `model_response.schema.json`.
- **Prompt policy records**: define what content may and may not be sent to each model provider.

## Model routing

Model selection is deterministic given the same inputs. The routing function considers:

1. **Capability match**: the selected model MUST support the required task type (generation, classification, embedding, etc.).
2. **Cost**: prefer lower-cost models when capability is equivalent.
3. **Reliability**: prefer models with higher recent success rates.
4. **Policy**: some models are restricted by tenant or workspace policy (e.g., data residency, provider allowlist).

Rules:
- Model routing MUST be deterministic for identical inputs and identical provider state.
- The routing decision MUST be recorded in the invocation record.
- If no model satisfies all constraints, the invocation MUST fail with `no_eligible_model`.

## Output validation

Model outputs carry `TrustClass: bounded_external`. They are treated as external inferences, not facts.

Rules:
- Every model response MUST have a `validation_status`: `passed`, `failed`, or `pending`.
- Validation checks structural conformance, safety policy compliance, and value-range plausibility.
- A response with `validation_status: failed` MUST NOT be forwarded to downstream consumers.
- Model output MUST NOT be promoted directly into trusted or plannable knowledge. It enters the Memory Plane only through the Learning Admission gate.

## Cost control

- Every invocation MUST record an estimated cost before the call and an actual cost after.
- The plane enforces per-tenant and per-workspace budget limits.
- When a budget limit is reached, further invocations are rejected with `budget_exceeded` until the limit is raised or the period resets.
- Cost tracking MUST be monotonic: recorded costs MUST NOT decrease.

## Fallback ordering

When the primary model is unavailable, the plane follows a deterministic fallback sequence.

Rules:
- The fallback sequence MUST be declared in configuration, not computed at runtime.
- Each fallback candidate MUST satisfy the same capability and policy constraints as the primary.
- The plane MUST record which model in the sequence was actually used.
- If all models in the sequence are unavailable, the invocation fails with `all_models_unavailable`.
- Fallback MUST NOT silently downgrade capability. If the fallback model lacks a required capability, the invocation fails.

## Policy hooks

- **Prompt policy**: defines what content may be sent to each model provider. PII stripping, data residency rules, and content restrictions are enforced before the prompt leaves the platform.
- **Output validation policy**: defines structural and semantic checks applied to model responses.
- **Cost approval**: invocations above a declared cost threshold require explicit approval.

## Failure modes

| Mode | Meaning | Recoverability |
|---|---|---|
| `model_unavailable` | Primary model is unreachable or returning errors. | Failover to next in fallback sequence. |
| `timeout` | Model did not respond within the declared deadline. | Retryable or failover. |
| `malformed_response` | Model response does not conform to expected structure. | Not retryable without provider fix. |
| `budget_exceeded` | Tenant or workspace budget limit reached. | Not retryable until budget is raised or period resets. |
| `output_validation_failed` | Response failed structural, safety, or plausibility checks. | Not retryable. Response is discarded. |
| `no_eligible_model` | No model satisfies capability and policy constraints. | Not retryable without configuration change. |
| `all_models_unavailable` | Every model in the fallback sequence is unavailable. | Retryable after backoff. |

Every failure MUST be recorded in the model response record and linked to the originating trace.

## Prohibitions

- MUST NOT promote model output directly into trusted or plannable knowledge without passing through the Learning Admission gate.
- MUST NOT invoke models without a prompt policy check.
- MUST NOT bypass cost controls. Every invocation counts against the budget.
- MUST NOT send content to a model provider that violates the prompt policy for that provider.
- MUST NOT cache model responses as deterministic facts. Model outputs are non-deterministic inferences.
- MUST NOT hide fallback decisions from the trace. The actual model used MUST be recorded.

## Dependencies

- Governance Plane: prompt policy, output validation policy, cost thresholds, provider allowlists.
- External Integration Plane: model providers are external connectors. Invocations use MXI infrastructure.
- Memory Plane: model outputs enter long-term knowledge only through Learning Admission.
- Capability Plane: model capability declarations.
