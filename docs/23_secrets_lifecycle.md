# 23 — Secrets / Config Lifecycle

## Purpose

Govern how secrets are sourced, scoped, masked, and protected from
accidental persistence throughout the MCOI runtime.  Every credential,
API key, token, or other sensitive value must pass through this lifecycle
so the platform can guarantee that secret material never leaks into
logs, traces, serialized artifacts, error messages, or telemetry.

## Secret Sources

| Source           | Description                                          |
|------------------|------------------------------------------------------|
| `environment`    | Value read from an environment variable at startup.  |
| `file`           | Value read from a local file path (e.g. `.env`).     |
| `vault`          | Reference resolved from an external vault service.   |
| `operator_input` | Value supplied interactively by the human operator.  |

The runtime treats all sources identically once ingested; the source
tag is metadata for audit and rotation policy only.

## Secret Scope

Every secret is bound to a **provider_id + credential_scope_id** pair.
This binding ensures that:

- A secret registered for provider A cannot be resolved by provider B.
- Credential scopes (defined in `contracts/provider.py`) declare the
  permission boundary; the secret lifecycle enforces it.
- Scope mismatch is a hard error, never a silent fallback.

## Masking Rules

Secrets must **never** appear in:

1. Log output (any level).
2. Trace records or replay artifacts.
3. Operator-facing reports or summaries.
4. Serialized persistence artifacts (JSON, snapshot, export).
5. Error messages or exception payloads.
6. Telemetry events.

The `MaskedValue` type enforces masking at the representation layer:
`__repr__` and `__str__` always return `***MASKED***`.  The actual
value is accessible only through the explicit `reveal()` method.

## Persistence Protection

Fields marked as secret are excluded from serialization:

- `SecretReference` carries only `secret_id` and `scope_id` — never the
  actual value.
- The `SecretSerializer.scan_for_secrets()` utility scans a dict tree
  for embedded secret values before any write and raises if found.
- The `SecretSerializer.mask_secrets()` utility produces a sanitized
  copy suitable for persistence or display.
- `SecretPolicy.never_persist` (default `True`) is the authoritative
  flag; serialization code must consult it.

## Rotation

- Each `SecretDescriptor` carries an optional `expires_at` timestamp.
- `SecretPolicy.rotation_warning_days` (default 30) controls how far
  in advance the runtime surfaces expiring secrets via
  `SecretStore.list_expiring()`.
- Status transitions: `active` -> `rotation_pending` -> `active` (after
  replacement) or `active` -> `expired` / `revoked`.

## Prohibitions

1. No secret in plain text in any persisted artifact.
2. No secret in error messages or exception `args`.
3. No secret in telemetry payloads or metric labels.
4. No secret logged at any verbosity level.
5. No secret transmitted outside the declared credential scope.
