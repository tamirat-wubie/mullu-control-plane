# Provider Configuration

Scope: all Mullu Platform modules that connect to external providers (APIs, communication services, model hosts).

Providers are the bridge between governed abstractions and real external systems. Without explicit provider configuration and credential scope, integrations become ungoverned side channels.

## Purpose

Define how external providers are registered, configured, credentialed, and governed.

## Owned artifacts

- `ProviderDescriptor` — identity, class, and configuration of a registered provider.
- `CredentialScope` — the declared permission boundary of a provider's credentials.
- `ProviderHealthRecord` — current health/availability state of a provider.

## Provider classes

- `integration` — external API/SaaS providers (MXI).
- `communication` — message delivery providers (MCCI).
- `model` — LLM/model inference providers (MMOI).

## Provider descriptor rules

1. Every provider MUST carry a unique `provider_id` and explicit `provider_class`.
2. Every provider MUST reference a `credential_scope_id` that declares its permission boundary.
3. Providers MUST be explicitly `enabled` or `disabled`. No implicit default.
4. Provider configuration MUST be explicit and inspectable, not hidden in environment variables.

## Credential scope rules

1. A `CredentialScope` declares what a provider is allowed to access.
2. Scope MUST include: allowed base URLs (for HTTP), allowed operations, rate limits.
3. Credentials MUST NOT be used outside their declared scope.
4. Credential rotation MUST NOT break running operations. Scope identity is stable across rotations.
5. Credential values (secrets, tokens) MUST NOT appear in contracts, traces, or persistence. Only `credential_scope_id` is stored.

## Provider health rules

1. Provider health MUST be tracked as `healthy`, `degraded`, `unavailable`, or `unknown`.
2. Health MUST be updated from invocation results, not assumed.
3. Health status MUST be surfaced in the operator console and meta-reasoning.
4. A provider in `unavailable` state MUST NOT be invoked until health recovers.

## Policy hooks

- Provider enablement policy: who may enable/disable providers.
- Credential scope policy: what scope boundaries are permitted per provider class.
- Rate limit policy: maximum invocations per time window.
- Cost limit policy: maximum cost per invocation, per window, per tenant.

## Failure modes

- `provider_not_registered` — invocation targets an unknown provider.
- `provider_disabled` — invocation targets a disabled provider.
- `credential_scope_exceeded` — operation falls outside declared scope.
- `rate_limit_exceeded` — too many invocations in the current window.
- `provider_unavailable` — provider health is unavailable.

## Prohibited behaviors

- MUST NOT invoke providers without checking enabled state.
- MUST NOT use credentials outside their declared scope.
- MUST NOT store credential secrets in traces, persistence, or contracts.
- MUST NOT assume provider health without evidence from invocation results.
- MUST NOT bypass rate or cost limits.

## Dependencies

- Governance Plane: provider enablement and scope policies.
- Meta-Reasoning Plane: provider health feeds capability confidence.
- Integration/Communication/Model planes: consume provider configuration.
