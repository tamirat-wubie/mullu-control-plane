<!--
Purpose: Record the private Govern Cloud staging deployment evidence gathered on 2026-06-11.
Governance scope: private Render service witness, managed PostgreSQL dependency,
  gateway integration boundary, and no-publication constraints.
Dependencies: DEPLOYMENT_STATUS.md, .env.example, gateway/server.py, Render
  service logs, and operator-entered secret values that are not serialized here.
Invariants: no secret values are recorded; api.mullusi.com remains unchanged;
  public DNS and public production health are not mutated by this witness.
-->

# Govern Cloud Private Staging Witness - 2026-06-11

## Summary

This witness records a private Render staging deployment for Govern Cloud. It is
not a public production declaration and does not replace the existing
`api.mullusi.com` gateway witness in `DEPLOYMENT_STATUS.md`.

| Surface | Evidence | State |
|---|---|---|
| Private service name | `mullusi-govern-cloud-staging` | SolvedVerified |
| Render service id | `srv-d8lb18flk1mc73cohnd0` | SolvedVerified |
| Render deploy id | `dep-d8lb18nlk1mc73cohns0` | SolvedVerified |
| Container image | `ghcr.io/mullusi/mullusi-govern-cloud:v2026.06.11-govern-cloud.1` | SolvedVerified |
| Image commit label | `21e4314` | SolvedVerified |
| Internal address | `mullusi-govern-cloud-staging:8000` | SolvedVerified |
| Managed database | `mullu-pilot-postgres`, `Basic-256mb` | SolvedVerified |
| Public API binding | `api.mullusi.com` unchanged | Pass |
| DNS mutation | none | Pass |

## Runtime Evidence

The Render shell health probe returned:

```json
{"status":"ok","service":"mullusi-govern-cloud-staging"}
```

The first runtime conformance pass detected missing PostgreSQL schema tables and
kept the release gate blocked. The schema was then applied inside the service:

```text
schema_apply_passed state=applied schema_hash=700b9590ddb7e2c04211a3477cafeda106084a62440aef3e23eac21c6d5dc15c detail=schema.sql applied
```

The post-schema runtime conformance result was:

| Finding | State | Detail |
|---|---|---|
| `required_environment` | pass | complete |
| `image` | pass | tag `v2026.06.11-govern-cloud.1` |
| `MULLUSI_DEV_API_KEY` | pass | configured |
| `MULLUSI_OPERATOR_API_KEY` | pass | configured |
| `MULLUSI_PROOF_SIGNING_KEY` | pass | configured |
| `database_url` | pass | remote PostgreSQL configured |
| `persistence_policy` | pass | required |
| `allowed_origins` | pass | count `4` |
| `database_schema` | pass | PostgreSQL schema ready |

Runtime result: `SolvedVerified`.
Release gate: `ready`.

## Post-Merge Closure Evidence

The private staging witness was merged into `main` through PR #1519:

```text
merge_commit=e092e041939e28a4eaeb4a570e0c9b985b0c83d8
run_id=27365204546
workflow=CI - Build Verification
conclusion=success
```

The post-merge `main` CI run completed successfully after the GitHub Actions
budget gate was restored. The run covered the gateway witness tests, SDLC
governance gate, schema validation, Python shards, Rust tests, TypeScript SDK
verification, release status validation, deployment publication closure check,
gateway deployment environment check, and gateway ingress manifest check.

Render logs for deploy `dep-d8lb18nlk1mc73cohns0` showed the service starting,
binding to port `8000`, and becoming live. Later log lines showed successful
internal probes:

```text
GET /health HTTP/1.1 -> 200 OK
GET /runtime/conformance HTTP/1.1 -> 200 OK
```

Render events showed the service on the `Starter` plan using image
`ghcr.io/mullusi/mullusi-govern-cloud:v2026.06.11-govern-cloud.1`.

Render Shell remains intentionally unopened for further direct terminal work
because the page requires adding an account SSH public key. Current closure does
not require that account-access change because CI, deploy logs, and conformance
logs already establish the private staging witness.

## Gateway Boundary

The control-plane gateway has an operator-gated read model at:

```text
/govern-cloud/staging/witness
```

That route is intentionally not a public proxy. It reports only private
dependency configuration state and never serializes secret values. The route
requires authority-operator authorization outside explicit local/test runtime.

The gateway also contains a separately gated public read proxy for exactly two
Govern Cloud paths:

```text
GET /v1/health
GET /v1/version
```

Those routes are disabled unless both `MULLU_GOVERN_CLOUD_STAGING_ENABLED` and
`MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED` are truthy. The proxy validates that
`MULLU_GOVERN_CLOUD_INTERNAL_URL` is a base HTTP(S) URL without credentials,
query, fragment, or path prefix; forwards no caller authorization headers; and
accepts only bounded JSON object responses from the private service. No
arbitrary `/v1/*` forwarding is allowed.

Required environment bindings:

```text
MULLU_GOVERN_CLOUD_STAGING_ENABLED=true
MULLU_GOVERN_CLOUD_INTERNAL_URL=http://mullusi-govern-cloud-staging:8000
MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED=false
MULLU_GOVERN_CLOUD_RENDER_SERVICE_ID=srv-d8lb18flk1mc73cohnd0
MULLU_GOVERN_CLOUD_RENDER_DEPLOY_ID=dep-d8lb18nlk1mc73cohns0
MULLU_GOVERN_CLOUD_IMAGE_TAG=ghcr.io/mullusi/mullusi-govern-cloud:v2026.06.11-govern-cloud.1
MULLU_GOVERN_CLOUD_DATABASE_PLAN=Basic-256mb
```

## Publication Decision

Public publication remains `AwaitingEvidence` until the gateway deployment is
explicitly configured with:

```text
MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED=true
```

and a live gateway integration witness proves:

1. the gateway can reach the private service from Render;
2. only `/v1/health` and `/v1/version` are publicly forwarded;
3. production evidence does not expose raw secrets, database URLs, tokens, or
   private headers;
4. rollback is documented;
5. an operator approves the public API binding.

## Rollback

Rollback does not require DNS changes because no DNS mutation was made.

1. Set `MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED=false` on the gateway to close
   the public read proxy.
2. If private staging itself must be disabled, set
   `MULLU_GOVERN_CLOUD_STAGING_ENABLED=false` on the gateway.
3. Redeploy the gateway.
4. Keep the private Govern Cloud service running for forensic review, or suspend
   the Render service if the operator approves cost reduction.

## Status

Outcome: `SolvedVerified` for private staging runtime evidence and post-merge
CI.
Public production outcome: `AwaitingEvidence`.
Next action: deploy the allowlisted public read proxy, set
`MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED=true` only after operator approval, and
collect live `/v1/health` plus `/v1/version` evidence before declaring
`api.mullusi.com` Govern Cloud publication complete.
