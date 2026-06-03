# Mullu Platform — Production Deployment Guide

**Audience:** operators deploying the Mullu Control Plane to pilot or production
**Status:** authoritative as of v4.37.0
**Companion docs:** [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md) (pre-flight tickbox), [`MAF_RECEIPT_COVERAGE.md`](MAF_RECEIPT_COVERAGE.md) (receipt coverage invariant)

This document is the deployment-time reference for the audit-grade hardening shipped between v4.26 and v4.37. Every required env var, every error code introduced by an audit fix, every capacity-sizing number is here. If you're deploying for the first time, read this end-to-end. If you're upgrading, read the [Upgrade matrix](#upgrade-matrix) and the env-var rows that changed.

---

## Quick start

Minimum viable production manifest:

```yaml
env:
  - name: MULLU_ENV
    value: "production"
  - name: MULLU_ENV_REQUIRED
    value: "true"
  - name: MULLU_DB_BACKEND
    value: "postgresql"
  - name: MULLU_DB_URL
    valueFrom: { secretKeyRef: { name: mullu-db, key: url } }
  - name: MULLU_DB_POOL_SIZE
    value: "10"
  - name: MULLU_CORS_ORIGINS
    value: "https://app.example.com,https://admin.example.com"
  - name: MULLU_ALLOW_UNKNOWN_TENANTS
    value: "false"
  - name: MULLU_ENCRYPTION_KEY
    valueFrom: { secretKeyRef: { name: mullu-keys, key: encryption } }
  - name: MULLU_JWT_SECRET
    valueFrom: { secretKeyRef: { name: mullu-keys, key: jwt } }
  - name: MULLU_JWT_ISSUER
    value: "https://auth.example.com"
  - name: MULLU_JWT_AUDIENCE
    value: "mullu-api"
  - name: ANTHROPIC_API_KEY
    valueFrom: { secretKeyRef: { name: mullu-llm, key: anthropic } }
```

After deploy, verify:

```bash
curl https://your-host/health   # → {"status":"healthy"}  (liveness)
curl https://your-host/ready    # → 200 readiness; 503 when a dependency is down
# Promotion gate (opt-in): set MULLU_HEALTH_WITNESS_ENABLED=true, then
curl -X POST https://your-host/api/v1/health/witness  # → 200 {"outcome":"verified"}
```

If `MULLU_ENV_REQUIRED=true` but `MULLU_ENV` is missing, the platform refuses to start with `EnvBindingError`. That's intended.

---

## Environment variable reference

Variables are grouped by purpose. Every row marks whether the variable is **required** in production, what audit fracture it relates to (if any), and what happens if you get it wrong.

### Core environment binding

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_ENV` | **yes (production)** | `local_dev` | Must be `local_dev` / `test` / `pilot` / `production`. Unknown values fall to sandboxed shell policy with an ERROR log. F5. |
| `MULLU_ENV_REQUIRED` | **yes (production)** | unset | Set to `true`/`1`/`yes`/`on` to make missing `MULLU_ENV` a hard `EnvBindingError` at boot rather than a silent `local_dev` fallback. F5 hardening from v4.35. |

### Persistence

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_DB_BACKEND` | **yes (production)** | `memory` | `memory` / `sqlite` / `postgresql`. Production must be `postgresql` — `memory` triggers a startup warning in non-dev envs. **Note:** value is `postgresql` (not `postgres`). |
| `MULLU_DB_URL` | **yes (postgresql)** | unset | psycopg2 DSN, e.g. `postgresql://user:pass@host:5432/mullu`. |
| `MULLU_DB_POOL_SIZE` | recommended | `1` | Per-store connection-pool cap. v4.36 added pool support to governance stores; v4.37 to the primary store. **Total PG connections = `replicas × 5 × pool_size`** (4 governance stores + 1 primary). Defaults to 1 = legacy single-conn (with the v4.37 lock fix). Typical production value: 5–10. F12. |

### Authentication

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_JWT_SECRET` | recommended | unset | Base64-encoded HMAC secret for HS256/HS384/HS512. When set, JWT auth is enabled. v4.33 hardened: empty `sub` / empty tenant claim / future `iat` rejected. |
| `MULLU_JWT_ISSUER` | yes (if JWT) | `mullu` | Expected `iss` claim. |
| `MULLU_JWT_AUDIENCE` | yes (if JWT) | `mullu-api` | Expected `aud` claim. |
| `MULLU_JWT_TENANT_CLAIM` | optional | `tenant_id` | JWT claim name carrying the tenant identifier. |
| `MULLU_API_AUTH_REQUIRED` | recommended | unset | When truthy, all `/api/*` requests must carry a valid Authorization header. F16-aligned. |
| `MULLU_ALLOW_WILDCARD_API_KEYS` | **no in production** | unset | When truthy, allows API keys with scope `*` to be created. Defense-in-depth: keep unset in production so wildcard keys must be explicitly minted via the admin path. |

### CORS / network

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_CORS_ORIGINS` | **yes (production)** | unset | Comma-separated allowlist. Wildcard `*` is rejected in `pilot`/`production`. Empty value in non-dev envs triggers a startup warning. |

### Tenant gating

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_ALLOW_UNKNOWN_TENANTS` | **no in production** | env-derived (`true` only in `local_dev`/`test`) | When truthy, a tenant_id never seen before passes the tenant gate. **Always `false` in production.** |

### Field encryption (audit at rest)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_ENCRYPTION_KEY` | **yes (production)** | unset | Base64-encoded 32-byte key for AES-GCM field encryption of audit `detail` JSONB. When unset, audit detail is stored plaintext. The startup posture validator warns loudly if encryption is unconfigured in non-dev envs. |

### Shell sandbox (governed code execution)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_SHELL_EXECUTION_ENABLED` | optional | `false` (effective) | When truthy AND `MULLU_ENV` is `pilot`/`production`, shell execution uses `PILOT_PROD` policy. When unset/false, uses `PILOT_PROD_DISABLED` (shell off). Unknown environments always fall to `SANDBOXED`. |

### Health / promotion witness

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_HEALTH_WITNESS_ENABLED` | optional | unset (off) | When truthy, exposes `POST /api/v1/health/witness` — an operator promotion gate that issues one bounded synthetic governed decision (tenant `system`), persists its proof + audit receipts, and verifies both (`200`/`"outcome":"verified"`, else `503`). Off by default so it is not an open ledger-write vector; enable only to run the promotion check. `/health` (liveness) and `/ready` (dependency-aware readiness) are always on. |

### Model provider configuration

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_LLM_BACKEND` | optional | auto-detect | Supports hosted providers plus `ollama`, `vllm`, `sglang`, `tgi`, `llamacpp`, `localai`, `lmstudio`, and `stub`. When unset, picks the first provider with a configured key or local base URL. Setting `stub` in pilot/production raises a hard error. |
| `MULLU_LLM_MODEL` | optional | `claude-sonnet-4-20250514` | Default model name for the chosen backend. |
| `MULLU_LLM_BUDGET_MAX_COST` | optional | `100.0` | Default per-tenant cost budget (USD). Atomic budget enforcement from v4.27. F2. |
| `MULLU_LLM_BUDGET_MAX_CALLS` | optional | `10000` | Default per-tenant call cap. |
| `MULLU_LLM_MAX_TOKENS` | optional | `4096` | Per-call token cap. |
| `ANTHROPIC_API_KEY` | one provider required | unset | |
| `OPENAI_API_KEY` | " | unset | |
| `GEMINI_API_KEY` | " | unset | |
| `OLLAMA_BASE_URL` | " | unset | Local Ollama endpoint. |
| `VLLM_BASE_URL` / `VLLM_API_KEY` | " | unset | Private vLLM OpenAI-compatible endpoint; API key is optional unless the server enforces one. |
| `SGLANG_BASE_URL` / `SGLANG_API_KEY` | " | unset | Private SGLang OpenAI-compatible endpoint; API key is optional unless the server enforces one. |
| `TGI_BASE_URL` / `TGI_API_KEY` | " | unset | Hugging Face TGI Messages API endpoint; API key is optional for local servers. |
| `LLAMACPP_BASE_URL` / `LLAMACPP_API_KEY` | " | unset | llama.cpp OpenAI-compatible endpoint. |
| `LOCALAI_BASE_URL` / `LOCALAI_API_KEY` | " | unset | LocalAI OpenAI-compatible endpoint. |
| `LMSTUDIO_BASE_URL` / `LMSTUDIO_API_KEY` | " | unset | LM Studio local server endpoint. |

### Background workers / certification

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_CERT_ENABLED` | optional | `true` | Periodic certification daemon. |
| `MULLU_CERT_INTERVAL` | optional | `300` (seconds) | Certification cadence. Set to `0` in tests to disable. |
| `MULLU_PII_SCAN` | optional | `true` | PII scanner on input/output content. |

### Governed swarm route mount

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_GOVERNED_SWARM_ENABLED` | optional | unset / disabled | Optional governed swarm route mount. The route surface is disabled by default and mounts only when explicitly truthy. |
| `MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH` | yes, if enabled | unset | Absolute append-only `.jsonl` audit file path for governed swarm run receipts. Use persistent storage in pilot and production. The parent directory must already exist and be writable before startup. |
| `MULLU_GOVERNED_SWARM_RUNTIME_PATH` | optional | unset | Runtime bridge for non-standard checkouts. Set to this repository's `mcoi` directory only when the installed package cannot import bundled `mcoi_runtime/swarm`. |

Enabled routes:

```text
POST /api/v1/swarm/invoice-runs
GET  /api/v1/swarm/runs/{run_id}
GET  /api/v1/swarm/runs
```

Operator posture:

```text
GET /api/v1/health/extensions
```

The extension health read model reports governed swarm and note-memory
registration, enablement, mount state, and path-configuration booleans without
exposing raw filesystem paths for audit-store or note-memory storage.

Operational rule:

```text
No audit store path, no governed swarm mount.
Relative audit store path, no governed swarm mount.
Audit store path without .jsonl extension, no governed swarm mount.
Audit store parent missing or not writable, no governed swarm mount.
No runtime path containing mcoi_runtime/swarm, no optional runtime bridge.
```

Use `examples/governed_swarm_control_plane.env.example` as the redacted
operator template for this feature.

Current runtime witness:

```text
Repository: tamirat-wubie/mullu-control-plane
Runtime label: control-plane-bundled-runtime
Runtime path after checkout: <checkout>/mcoi
```

Promotion rule:

```text
Pilot promotion requires a SolvedVerified governed swarm staging evidence bundle
and a SolvedVerified governed swarm promotion readiness report.
Production promotion is not granted by the staging promotion report; production
must also pass the deployment witness and public production health declaration gates.
```

Validation command:

```bash
python scripts/validate_governed_swarm_promotion_readiness.py \
  --staging-evidence-bundle ".change_assurance/governed_swarm_staging_evidence_bundle.json" \
  --target-environment pilot \
  --output ".change_assurance/governed_swarm_promotion_readiness.json" \
  --strict
```

### State directories

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MULLU_STATE_DIR` | optional | tempdir | Persistence root for capability state. Mount to a PVC in production. |
| `MULLU_DATA_DIR` | optional | tempdir | Coordination scratch space. |
| `MULLU_COORDINATION_DIR` | optional | derived from `MULLU_DATA_DIR` | Coordination engine state. |

### Gateway channels (optional, install per channel)

| Variable group | Channel |
|---|---|
| `WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_APP_SECRET` | WhatsApp |
| `SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET` | Slack |
| `TELEGRAM_BOT_TOKEN` | Telegram |
| `DISCORD_BOT_TOKEN` + `DISCORD_PUBLIC_KEY` | Discord |

---

## Audit-fracture → env-var mapping

If you've read the audit report and want to verify each fracture's mitigation is wired:

| Fracture | Status | Required env-var setting in production |
|---|---|---|
| F2 atomic budget | v4.27 | `MULLU_DB_BACKEND=postgresql` (atomic SQL UPDATE only kicks in on PG) |
| F3 audit checkpoint | v4.28 | `MULLU_DB_BACKEND=postgresql` |
| F4 atomic audit append | v4.31 | `MULLU_DB_BACKEND=postgresql` + `MULLU_ENCRYPTION_KEY` for at-rest |
| F5 env binding | v4.35 | `MULLU_ENV=production` + `MULLU_ENV_REQUIRED=true` |
| F6 tenant binding | v4.35 | (automatic — middleware sets `tenant_id_explicit` per-request) |
| F9 webhook SSRF | v4.32 | (automatic — unified SSRF policy applies to webhook subscribe + delivery) |
| F10 DNS rebinding | v4.32 | (automatic — http_connector pins resolved IP) |
| F11 atomic rate limit | v4.29 + v4.34 | `MULLU_DB_BACKEND=postgresql` |
| F12 connection pool | v4.36 + v4.37 | `MULLU_DB_POOL_SIZE` ≥ 5 (recommended) |
| F15 atomic hash chain | v4.30 | `MULLU_DB_BACKEND=postgresql` |
| F16 musia_auth wiring | v4.26 | `MULLU_JWT_SECRET` + `MULLU_API_AUTH_REQUIRED=true` |
| JWT hardening | v4.33 | `MULLU_JWT_SECRET` (default flags reject empty `sub`/tenant + future `iat` + `http://` JWKS) |

If any row says "Status: vXY" but the mitigation isn't visible at runtime, you have a misconfiguration — see the troubleshooting section below.

---

## Capacity sizing

### PostgreSQL `max_connections`

Total connections from one Mullu replica:

```
per_replica = 4 (governance stores) + 1 (primary store) = 5 stores
total_pg_connections = replicas × 5 × MULLU_DB_POOL_SIZE
```

Examples:

| Replicas | `MULLU_DB_POOL_SIZE` | PG connections |
|---|---|---|
| 1 | 1 | 5 |
| 3 | 5 | 75 |
| 3 | 10 | 150 |
| 5 | 10 | 250 |
| 10 | 10 | 500 |

Managed PostgreSQL services typically default `max_connections` to 100–200. Aurora can go higher. **Verify your PG `max_connections` covers `total_pg_connections + headroom for ad-hoc tools (psql / pgAdmin / backups)`.**

If you need more concurrency than `max_connections` allows, put a connection pooler (PgBouncer in `transaction` mode) in front of PG and point `MULLU_DB_URL` at the pooler.

### Pool sizing heuristic

- Start at `pool_size=1` (default). Verify v4.37 deploys cleanly.
- Bump to `pool_size=5` for one bake cycle (a week or your shortest stable window).
- Tune up to `pool_size=10–20` per replica based on observed pool-exhaustion logs.
- Beyond 20: prefer adding replicas rather than growing the pool further. PG benefits from many short connections, not few fat ones.

### Memory footprint

Each Mullu replica with `pool_size=10`:
- Python heap: ~250 MB baseline + ~50 MB per active in-flight request
- 5 × 10 = 50 idle PG connections × ~3 MB each (libpq) = 150 MB
- Recommended container memory limit: 1 GiB

---

## Error codes & log signals reference

Every audit-grade rejection has a deterministic, bounded error string. Watch for these in your auth log + governance decision log.

### Auth-layer rejections (HTTP 401/403)

| String | Meaning | Action |
|---|---|---|
| `tenant mismatch` | Request supplied `X-Tenant-ID: B` (or `?tenant_id=B`) on a JWT/key authenticated as tenant A. | F6 v4.35. Either client is buggy (cross-tenant call from a logged-in session), or this is spoofing. |
| `sub claim is empty or missing` | JWT has empty `sub`. | F33 v4.33. Either IdP is misconfigured, or token was forged. |
| `tenant claim is empty or missing` | JWT has empty tenant claim. | F33 v4.33. Check IdP claim mapping. |
| `token iat is in the future` | JWT `iat` exceeds `now + clock_skew`. | F33 v4.33. Clock drift between IdP and Mullu, or forged token. |
| `iat claim must be numeric` | JWT `iat` is non-numeric. | Almost certainly a forged or buggy token. |
| `algorithm not allowed` | JWT signed with an algorithm outside `OIDCConfig.allowed_algorithms`. | Check IdP signing alg matches. |
| `signature verification failed` | JWT signature did not verify. | Wrong secret/key, or the token was tampered with. |
| `redirect_blocked:<code>` | http_connector saw a 3xx and refused to follow it. | F10 v4.32. Defensive — either the URL was supposed to be the canonical one, or someone tried to redirect into private space. |
| `jwks_redirect_blocked:<code>` | JWKS endpoint returned a 3xx. | v4.33. Either JWKS URL is wrong (point to canonical), or someone is trying to substitute keys. |
| `blocked_private_address` | http_connector or webhook delivery target resolved to a private/metadata IP. | F9/F10 v4.32. SSRF defense fired. |
| `blocked_private_address_at_connect:<ip>` | DNS pin caught a rebinding attempt at the socket layer. | F10 v4.32. Defense-in-depth catch — non-zero count means active DNS rebinding (or misconfigured DNS). |
| `policy_requires_https` | http_connector saw `http://` URL but policy required HTTPS. | Operator policy. |
| `response_too_large` | http_connector response exceeded policy `max_response_bytes`. | Operator policy. |

### Governance-guard rejections (HTTP 429/403)

| `blocking_guard` | Meaning |
|---|---|
| `rate_limit` | 429 — bucket exhausted. F11 v4.29/v4.34. |
| `budget` | 403 — tenant cost or call budget exhausted. F2 v4.27. |
| `tenant_gating` | 403 — tenant disabled or unknown (`MULLU_ALLOW_UNKNOWN_TENANTS=false`). |
| `tenant` | 400 — tenant_id failed validation (>128 chars). |
| `api_key` | 401 — invalid API key. |
| `jwt` | 403 — JWT validation failed (any reason above). |
| `rbac` | 403 — RBAC denied. |
| `lambda_input_safety` | 403 — content safety chain rejected the prompt/content. |

### Startup-time errors (cause boot to fail)

| Error | Meaning | Fix |
|---|---|---|
| `EnvBindingError: MULLU_ENV is not set and MULLU_ENV_REQUIRED=true` | F5 v4.35. Operator removed `MULLU_ENV` from manifest. | Set `MULLU_ENV=production` (or whatever was intended). |
| `RuntimeError: postgres schema migration N failed (...)` | One of the 4 governance migrations failed. | Check PG user has `CREATE TABLE` privilege; check schema isn't already partially-applied. |
| `RuntimeError: RS* algorithms require the 'cryptography' package` | JWT config says RS256/RS384/RS512 but cryptography extra not installed. | `pip install mcoi-runtime[encryption]`. |
| `ValueError: jwks_url must use HTTPS` | F33 v4.33. `jwks_url=http://...` rejected at config. | Use HTTPS. If you really need HTTP (in-cluster sidecar), set `require_https_jwks=False`. |
| `MULLU_LLM_BACKEND='stub' is forbidden in 'production'` | Stub LLM in non-dev env. | Pick a real provider. |

### Startup-time warnings (don't block boot, fix soon)

| Warning | Action |
|---|---|
| `MULLU_ENV is not set; falling back to 'local_dev'` (CRITICAL) | Set `MULLU_ENV` explicitly + `MULLU_ENV_REQUIRED=true`. |
| `MULLU_DB_BACKEND=memory in non-dev environment` | Switch to `postgresql`. State doesn't survive restarts. |
| `MULLU_CORS_ORIGINS contains wildcard` | Replace with explicit allowlist. |
| `MULLU_CORS_ORIGINS is empty in non-dev environment` | Set explicit allowlist. |
| `field encryption is not configured` | Set `MULLU_ENCRYPTION_KEY`. |
| `governance store connection failed` | PG unreachable at boot; store falls back to no-op. State writes are silently lost. **Always treat this as critical.** |
| `governance store pool putconn failed` | A connection was unhealthy when the pool tried to return it. Sporadic = transient PG issue; consistent = pool sizing or `idle_in_transaction_session_timeout` mismatch. |

---

## Monitoring & runbook hooks

### Health endpoints

| Endpoint | What it checks |
|---|---|
| `/health` | Process is alive. Use as Kubernetes `livenessProbe`. |
| `/ready` | Subsystems are ready (governance stores reachable, JWT loaded if configured, etc.). Use as `readinessProbe`. |
| `/api/v1/health/deep` | Component-by-component breakdown. Useful for status pages. |

### Metrics (Prometheus exposition)

Available at `/api/v1/metrics` once governance metrics are wired (default in production):

- `mullu_requests_total` — total requests
- `mullu_requests_governed` — requests that passed all guards
- `mullu_requests_rejected` — rejected by some guard
- `mullu_proof_bridge_certification_failures` — proof bridge couldn't certify a decision (non-fatal but indicates a bug)
- `mullu_decision_log_record_failures` — decision log couldn't persist (often correlates with PG issues)
- `mullu_request_analytics_record_failures` — request analytics failed

Plus the v4.21+ chain-evaluation latency histograms.

### Audit chain integrity check

```bash
curl https://your-host/api/v1/audit/chain/verify
# → {"verified": true, "entries": 12345, "checkpoint": "..."}
```

The `checkpoint` field is the v4.28 anchor. Verification re-walks the hash chain from the most recent checkpoint forward.

---

## Upgrade matrix

If you're at an older version, apply these env-var changes when upgrading:

| Upgrading from → to | Required env-var changes |
|---|---|
| `< v4.26` → `≥ v4.26` | Set `MULLU_API_AUTH_REQUIRED=true` once you've migrated callers to send `Authorization`. Pre-v4.26 dev mode allowed unauthenticated access. |
| `< v4.27` → `≥ v4.27` | None. Atomic budget enforcement is automatic on PG. |
| `< v4.32` → `≥ v4.32` | None. Test code may need updates if it used unresolvable webhook URLs (`http://x`); use real-resolvable hostnames. |
| `< v4.33` → `≥ v4.33` | Confirm your IdP populates `sub` and your `tenant_claim`. If you have a non-compliant IdP, set `OIDCConfig(require_subject=False, require_tenant_claim=False)` programmatically — but production should always reject those. |
| `< v4.35` → `≥ v4.35` | **Add `MULLU_ENV_REQUIRED=true`.** Audit clients sending `X-Tenant-ID` that disagree with the JWT — they now get 403. |
| `< v4.36` → `≥ v4.36` | Optionally set `MULLU_DB_POOL_SIZE`. Without it, governance stores stay single-conn (safe but slow). |
| `< v4.37` → `≥ v4.37` | Same `MULLU_DB_POOL_SIZE` env var now also sizes the primary store pool. Re-validate PG `max_connections` budget. |

---

## Troubleshooting

### "I see `MULLU_ENV is not set; falling back to 'local_dev'` in production logs"

You forgot `MULLU_ENV` in the manifest. Add `MULLU_ENV=production` and `MULLU_ENV_REQUIRED=true` together.

### "Tests pass locally but production rejects every request with `tenant mismatch`"

Either your client is sending a stale `X-Tenant-ID` header, or your IdP is issuing tokens for a different tenant than the one the client thinks it's calling. Check the JWT payload's tenant claim against the client's `X-Tenant-ID` value.

### "Pool exhaustion under load"

`MULLU_DB_POOL_SIZE` is too low for your throughput. Symptoms: requests block waiting for `pool.getconn()`. Increase pool size, but verify PG `max_connections` covers it (or add a PgBouncer).

### "PG `idle_in_transaction_session_timeout` is killing pool connections"

The pool is serving stale connections. Either reduce PG's timeout, increase pool keepalive (libpq `keepalives` params in DSN), or add a `BEFORE` trigger on connection acquisition that pings PG. Long-term, run with `transaction`-mode PgBouncer.

### "I want to verify the v4.35 fail-closed env binding works"

```bash
docker run --rm \
  -e MULLU_ENV_REQUIRED=true \
  -e MULLU_DB_BACKEND=memory \
  mullu-control-plane:v4.37
# → EnvBindingError: MULLU_ENV is not set and MULLU_ENV_REQUIRED=true
```

If the container starts instead of exiting with `EnvBindingError`, your image is older than v4.35.

### "Audit chain reports `verified: false`"

Either the chain was tampered with, or a v4.28-pre-dating prune wiped the genesis anchor. Restore from backup. The v4.28 checkpoint anchor prevents this for new prunes; for old data, you may need to re-anchor manually.

---

## Soft rollout sequence (mandatory)

Even for patch releases, follow:

1. **Shadow / non-prod canary (1 week)** — deploy to a non-prod cluster with production traffic mirrored. Verify no new error-code spikes.
2. **5% canary in production (1 week)** — gradually shift traffic. Monitor:
   - `mullu_requests_rejected` rate (should not increase)
   - PG connection count (should match expected `replicas × 5 × pool_size`)
   - Auth log error-code distribution (any new codes warrant investigation)
3. **25% / 50% / 100% rollout (3 days each)** — bump traffic share, watch the same signals.
4. **Lock the version for at least 7 days at 100% before the next bump.**

For audit-grade hardening releases (any v4.2x – v4.3x), treat the rollout as if it were a major version. The fail-closed posture changes are intentional and not all of them are reversible without a downgrade.

---

## Where to go next

- **Receipt coverage invariant:** [`MAF_RECEIPT_COVERAGE.md`](MAF_RECEIPT_COVERAGE.md)
- **Atomic store doctrine:** [`ATOMIC_STORE_DOCTRINE.md`](ATOMIC_STORE_DOCTRINE.md) (the v4.27/v4.29/v4.30/v4.31 atomic-SQL series)
- **Pre-flight checklist:** [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md)
- **Release notes (chronological):** [`/RELEASE_NOTES_v4.*.md`](../) — start at v4.26 for the audit-fracture series

If something in this doc is wrong, file a PR. The deployment guide lives next to the code so the two stay in sync.
