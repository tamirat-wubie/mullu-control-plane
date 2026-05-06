# Deployment Matrix

## Profiles

| Profile | DB Backend | LLM Backend | CORS | Secrets | Use Case |
|---------|-----------|-------------|------|---------|----------|
| **local_dev** | SQLite (or memory) | stub | localhost:3000,8080 | Not required | Local development, unit tests |
| **test** | memory | stub | localhost | Not required | CI, integration tests |
| **pilot** | SQLite or PostgreSQL | stub or real provider | Explicit origins | `.env` file | Staging, demos, internal pilots |
| **production** | PostgreSQL (required) | Anthropic / OpenAI | Explicit origins (required) | Vault / secrets manager | Production workloads |

## Environment Variables

### Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `MULLU_ENV` | Environment profile | `production` |
| `MULLU_DB_BACKEND` | Database backend | `postgresql` |
| `MULLU_DB_URL` | Database connection string | `postgresql://mullu:$PW@db:5432/mullu` |
| `MULLU_CORS_ORIGINS` | Comma-separated allowed origins | `https://app.mullu.io` |
| `MULLU_ENCRYPTION_KEY` | Base64-encoded 32-byte field-encryption key | `openssl rand -base64 32` |
| `POSTGRES_PASSWORD` | Database password (compose) | Set in `.env` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MULLU_LLM_BACKEND` | `stub` | LLM provider: `stub`, `anthropic`, `openai` |
| `MULLU_LLM_MODEL` | `claude-sonnet-4-20250514` | Default model |
| `MULLU_LLM_BUDGET_MAX_COST` | `100.0` | Max LLM cost per budget |
| `MULLU_LLM_BUDGET_MAX_CALLS` | `10000` | Max LLM calls per budget |
| `MULLU_STATE_DIR` | system temp | Directory for state snapshots |
| `MULLU_CERT_INTERVAL` | `300` | Certification daemon interval (seconds) |
| `MULLU_CERT_ENABLED` | `true` | Enable certification daemon |
| `MULLU_API_AUTH_REQUIRED` | profile-based | Require `Authorization: Bearer <api-key>` on `/api/*`. Defaults to `false` in `local_dev` and `test`, `true` in `pilot` and `production` |
| `MULLU_GATEWAY_APPROVAL_SECRET` | — | Required outside `local_dev` and `test` if you use the raw gateway approval callback endpoint (`/webhook/approve/{request_id}`) |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (when backend=anthropic) |
| `OPENAI_API_KEY` | — | OpenAI API key (when backend=openai) |

| `MULLU_COMMAND_LEDGER_BACKEND` | `MULLU_DB_BACKEND` | Command ledger backend: `memory` or `postgresql` |
| `MULLU_COMMAND_LEDGER_DB_URL` | `MULLU_DB_URL` | Optional dedicated PostgreSQL URL for command ledger storage |
| `MULLU_TENANT_IDENTITY_BACKEND` | `MULLU_DB_BACKEND` | Tenant identity backend: `memory` or `postgresql` |
| `MULLU_TENANT_IDENTITY_DB_URL` | `MULLU_DB_URL` | Optional dedicated PostgreSQL URL for channel subject to tenant identity mappings |
| `MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY` | profile-based | Require a persistent, available tenant identity store. Defaults to true in `pilot` and `production` |
| `MULLU_GATEWAY_DEFER_APPROVED_EXECUTION` | `false` | If true, approved commands are queued for `gateway.worker` instead of executed inline |
| `MULLU_GATEWAY_WORKER_ID` | `gateway-worker` | Stable worker identity for command leases |
| `MULLU_GATEWAY_WORKER_BATCH_SIZE` | `10` | Max commands claimed per worker pass |
| `MULLU_GATEWAY_WORKER_LEASE_SECONDS` | `300` | Lease duration for claimed commands |
| `MULLU_GATEWAY_WORKER_POLL_SECONDS` | `2.0` | Worker polling interval |
| `MULLU_COMMAND_ANCHOR_SECRET` | unset | HMAC secret used by `gateway.worker` to sign command-event anchors |
| `MULLU_COMMAND_ANCHOR_KEY_ID` | `local` | Key identifier recorded on command-event anchors |
| `MULLU_REQUIRE_COMMAND_ANCHOR` | profile-based | Require command-event anchor signing. Defaults to true in `pilot` and `production` |
| `MULLU_RUNTIME_WITNESS_SECRET` | unset | HMAC secret used by `/gateway/witness` and `/runtime/witness` |
| `MULLU_RUNTIME_WITNESS_KEY_ID` | `runtime-witness-local` | Key identifier recorded on runtime witness objects |
| `MULLU_RUNTIME_CONFORMANCE_SECRET` | unset | HMAC secret used to verify runtime conformance witness collection |
| `MULLU_CAPABILITY_WORKER_URL` | unset | Restricted worker endpoint for dangerous capability execution, for example `http://capability-worker:8010/capability/execute` |
| `MULLU_CAPABILITY_WORKER_SECRET` | unset | HMAC secret shared by gateway and restricted capability worker |
| `MULLU_CAPABILITY_WORKER_TIMEOUT_SECONDS` | `10.0` | HTTP timeout for restricted capability worker calls |

## Quick Start

### Local Development

```bash
cd mcoi
pip install -e ".[dev]"
python -m pytest tests/ -m "not soak"
uvicorn mcoi_runtime.app.server:app --reload
```

### Docker Compose (Pilot)

```bash
# Create .env with required secrets
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)" > .env

docker compose up -d
curl http://localhost:8000/health
```

### Gateway Command Worker

Enable deferred approval execution when gateway callbacks should enqueue the
approved command and let a separate worker continue it:

```bash
export MULLU_GATEWAY_DEFER_APPROVED_EXECUTION=1
export MULLU_COMMAND_LEDGER_BACKEND=postgresql
export MULLU_COMMAND_ANCHOR_SECRET="$(openssl rand -hex 32)"
python -m gateway.worker
```

For one bounded pass, useful in smoke tests:

```bash
python -m gateway.worker --once --batch-size 5
```

### Restricted Capability Worker

Dangerous capabilities such as payment mutation must not execute inside the
gateway process in `pilot` or `production`. Run the restricted worker as a
separate process and point the gateway and gateway worker at it:

```bash
export MULLU_CAPABILITY_WORKER_SECRET="$(openssl rand -hex 32)"
export MULLU_CAPABILITY_WORKER_URL="http://localhost:8010/capability/execute"
python -m uvicorn gateway.capability_worker:app --host 0.0.0.0 --port 8010
```

Then validate the gateway deployment profile:

```bash
python scripts/validate_gateway_deployment_env.py --strict
```

After gateway and capability worker are running, run the runtime smoke probe:

```bash
export MULLU_GATEWAY_URL="http://localhost:8001"
export MULLU_CAPABILITY_WORKER_URL="http://localhost:8010/capability/execute"
python scripts/gateway_runtime_smoke.py
```

Before claiming pilot readiness, emit the local proof-slice witness:

```bash
python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json
```

The proof slice sends one deterministic tenant-scoped web message through the
gateway router, command ledger, causal closure kernel, terminal certificate,
closure memory promotion, and learning admission path. It is local deployment
evidence only; it does not replace live endpoint health evidence.

When a gateway endpoint is deployed, collect live deployment evidence:

```bash
export MULLU_GATEWAY_URL="https://gateway.example.com"
export MULLU_RUNTIME_WITNESS_SECRET="<runtime-witness-secret>"
python scripts/collect_deployment_witness.py \
  --gateway-url "$MULLU_GATEWAY_URL" \
  --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" \
  --expected-environment pilot \
  --output .change_assurance/deployment_witness.json
```

The collector probes `/health` and `/gateway/witness`, verifies the runtime
witness signature when the secret is supplied, and emits `published` only when
all evidence checks pass. Without signature verification, the deployment witness
fails closed as `not-published`.

The same collector can be run from GitHub Actions with
`.github/workflows/deployment-witness.yml`. Use the manual
`Deployment Witness Collection` workflow, provide the gateway URL and expected
environment, and configure the repository secret
`MULLU_RUNTIME_WITNESS_SECRET`. The workflow uploads
`.change_assurance/deployment_witness.json` as the `deployment-witness`
artifact.

Provision the runtime witness secret before dispatching the workflow:

```bash
python scripts/provision_runtime_witness_secret.py \
  --runtime-env-output .change_assurance/runtime_witness_secret.env
```

The provisioner generates a new secret from operating-system entropy, sets it
as the GitHub repository secret `MULLU_RUNTIME_WITNESS_SECRET`, and prints only
a fingerprint. It writes the runtime-side value only to the explicit ignored
env output path. Load that value into the deployed gateway runtime as
`MULLU_RUNTIME_WITNESS_SECRET`, then remove the local file after the runtime
secret manager is updated. If the runtime secret already exists, pipe it
through stdin instead of placing it in shell history:

```bash
printf "%s" "$MULLU_RUNTIME_WITNESS_SECRET" \
  | python scripts/provision_runtime_witness_secret.py --secret-stdin
```

Provision the live gateway target as repository variables once the endpoint is
known:

```bash
python scripts/provision_deployment_target.py \
  --gateway-url "https://gateway.example.com" \
  --expected-environment pilot
```

This sets `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` as GitHub
repository variables. The deployment witness dispatcher can use those variables
when local CLI arguments are omitted.

Publish the Kubernetes gateway route by rendering the ingress template with the
real DNS name:

```bash
python scripts/render_gateway_ingress.py \
  --gateway-host gateway.mullusi.com \
  --output .change_assurance/mullu-gateway-ingress.rendered.yaml
```

The renderer leaves `k8s/mullu-gateway-ingress.yaml` unchanged, writes an
ignored rendered manifest, and validates the rendered manifest without
placeholder allowance. To apply it in the same governed step, add `--apply`.

To reduce manual operator steps, dispatch the workflow and download the
artifact with the guarded shortcut:

```bash
python scripts/dispatch_deployment_witness.py
```

The dispatcher verifies that `MULLU_RUNTIME_WITNESS_SECRET` exists as a GitHub
repository secret and that the deployment witness workflow is active before it
dispatches the run. It resolves the gateway URL and expected runtime
environment from local arguments, environment variables, or GitHub repository
variables. It waits for the run to finish and downloads the
`deployment-witness` artifact into
`.change_assurance/deployment-witness-artifact`.

To collapse ingress rendering, target provisioning, and workflow dispatch into
one guarded operator action, run:

```bash
python scripts/orchestrate_deployment_witness.py \
  --gateway-host gateway.mullusi.com \
  --expected-environment pilot \
  --apply-ingress \
  --require-preflight \
  --dispatch
```

The orchestrator validates the host before writing repository variables, derives
`MULLU_GATEWAY_URL` from the validated host unless `--gateway-url` is provided,
keeps live cluster apply and workflow dispatch behind explicit flags, and
refuses dispatch when `--require-preflight` is present and readiness checks fail.

The same gated path is also available as the manual GitHub Actions workflow
`.github/workflows/gateway-publication.yml`. It accepts `gateway_host`,
`expected_environment`, `apply_ingress`, and `dispatch_witness` inputs. When
`apply_ingress` is true, the workflow requires `MULLU_KUBECONFIG_B64`; it always
requires `MULLU_RUNTIME_WITNESS_SECRET` to be mounted before the readiness gate.

Before dispatching that workflow, emit a machine-readable publication readiness
report:

```bash
python scripts/report_gateway_publication_readiness.py \
  --gateway-url "https://gateway.mullusi.com" \
  --expected-environment pilot \
  --dispatch-witness
```

The reporter derives the gateway host from explicit input or repository
variables, checks the runtime witness secret name, checks the optional
kubeconfig secret name only when `--apply-ingress` is requested, verifies the
workflow state and DNS resolution, writes
`.change_assurance/gateway_publication_readiness.json`, and prints the exact
`scripts/dispatch_gateway_publication.py` command to run next.

To dispatch directly from that witnessed report, run:

```bash
python scripts/dispatch_gateway_publication.py \
  --readiness-report .change_assurance/gateway_publication_readiness.json
```

The dispatcher fails closed unless the report has `ready: true`, belongs to the
selected repository, and contains the required publication fields. It then
re-validates secret presence and workflow state before dispatch.

To combine the readiness report and readiness-report dispatch handoff in one
operator command, run:

```bash
python scripts/publish_gateway_publication.py \
  --gateway-url "https://gateway.mullusi.com" \
  --expected-environment pilot \
  --dispatch-witness \
  --dispatch
```

The publisher writes `.change_assurance/gateway_publication_readiness.json`
before any workflow mutation, refuses dispatch when readiness is false, and
then dispatches from the written readiness report so the same handoff contract
is exercised. It also writes
`.change_assurance/gateway_publication_receipt.json` with the terminal local
decision state: ready-only, blocked-not-ready, or dispatched.

To validate the receipt as a dispatch-success gate, run:

```bash
python scripts/validate_gateway_publication_receipt.py \
  --receipt .change_assurance/gateway_publication_receipt.json \
  --require-ready \
  --require-dispatched \
  --require-success
```

The validator checks receipt structure, internal readiness consistency, terminal
state, optional expected repository/host/URL/environment values, and writes
`.change_assurance/gateway_publication_receipt_validation.json`.

To dispatch that GitHub workflow from a local operator shell and download the
`gateway-publication-witness` artifact, run:

```bash
python scripts/dispatch_gateway_publication.py \
  --gateway-host gateway.mullusi.com \
  --expected-environment pilot \
  --dispatch-witness
```

Add `--apply-ingress` only after `MULLU_KUBECONFIG_B64` is configured as a
repository secret for the target cluster.

Before dispatching the witness, run the preflight gate:

```bash
python scripts/preflight_deployment_witness.py \
  --gateway-host gateway.mullusi.com \
  --expected-environment pilot
```

The preflight writes `.change_assurance/deployment_witness_preflight.json` and
verifies DNS resolution, repository variables, runtime witness secret presence,
workflow state, `/health`, and `/gateway/witness`. To verify only DNS and
GitHub readiness before the ingress is live, add `--skip-endpoint-probes`.

The probe checks:

1. Gateway `/health`.
2. Gateway `/gateway/witness`.
3. Capability worker `/health`.
4. Signed `/capability/execute` request and signed worker response.

For local smoke testing without real payment credentials, the restricted worker
supports an explicit local/test-only stub:

```bash
export MULLU_ENV=local_dev
export MULLU_CAPABILITY_WORKER_ENABLE_SMOKE_STUB=1
```

Do not enable `MULLU_CAPABILITY_WORKER_ENABLE_SMOKE_STUB` in `pilot` or
`production`.

### Adapter Worker Packaging

Browser, document, voice, and email/calendar execution are packaged as
restricted worker services behind the `adapter-workers` compose profile. They
are not part of the default pilot startup path and must not be treated as
ambient gateway authority.

```bash
docker compose --profile adapter-workers up -d \
  browser-worker document-worker voice-worker email-calendar-worker
```

Required worker secrets:

```bash
MULLU_BROWSER_WORKER_URL=http://browser-worker:8020/browser/execute
MULLU_BROWSER_WORKER_SECRET=...
MULLU_DOCUMENT_WORKER_URL=http://document-worker:8030/document/execute
MULLU_DOCUMENT_WORKER_SECRET=...
MULLU_VOICE_WORKER_URL=http://voice-worker:8040/voice/execute
MULLU_VOICE_WORKER_SECRET=...
MULLU_EMAIL_CALENDAR_WORKER_URL=http://email-calendar-worker:8050/email-calendar/execute
MULLU_EMAIL_CALENDAR_WORKER_SECRET=...
MULLU_EMAIL_CALENDAR_WORKER_ADAPTER=production
EMAIL_CALENDAR_CONNECTOR_TOKEN=...     # optional governed connector token
EMAIL_CALENDAR_CONNECTOR_ID=gmail      # gmail, google_calendar, or microsoft_graph
EMAIL_CALENDAR_CONNECTOR_SCOPE_ID=...  # optional governed scope witness
GMAIL_ACCESS_TOKEN=...                 # optional Gmail connector credential
GOOGLE_CALENDAR_ACCESS_TOKEN=...       # optional Google Calendar connector credential
MICROSOFT_GRAPH_ACCESS_TOKEN=...       # optional Microsoft Graph connector credential
OPENAI_API_KEY=...
```

The gateway and `gateway.worker` build signed adapter clients only when both
the URL and matching secret for a worker are configured. A URL without its
secret fails closed during dispatcher construction. Leaving both unset keeps the
default pilot stack alive while those capabilities return `worker_unavailable`
receipts instead of executing raw tools in the gateway process.

The image installs worker dependencies through the `mcoi[all]` extra by
default. Set `MULLU_INSTALL_WORKER_DEPS=false` at build time only for API or
gateway images that intentionally exclude browser and document worker
dependencies. Playwright Chromium is installed only when both
`MULLU_INSTALL_WORKER_DEPS=true` and `MULLU_INSTALL_PLAYWRIGHT_BROWSERS=true`.
The email/calendar worker starts in production adapter mode with either
`EMAIL_CALENDAR_CONNECTOR_TOKEN` plus `EMAIL_CALENDAR_CONNECTOR_ID`, or the
provider-specific token names. Missing credentials fail closed per request and
still produce signed failure receipts.

The worker services expose:

| Worker | Port | Entry point |
|---|---:|---|
| Browser | `8020` | `gateway.browser_worker:app` |
| Document | `8030` | `gateway.document_worker:app` |
| Voice | `8040` | `gateway.voice_worker:app` |
| Email/calendar | `8050` | `gateway.email_calendar_worker:app` |

### Production Checklist

1. Set `MULLU_ENV=production`
2. Set `MULLU_DB_BACKEND=postgresql` with a real `MULLU_DB_URL`
3. Set `MULLU_CORS_ORIGINS` to your frontend domain(s)
4. Set `MULLU_ENCRYPTION_KEY` to a base64-encoded 32-byte key before startup
5. Set `POSTGRES_PASSWORD` via secrets manager (not `.env`)
6. Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` for real LLM
7. Verify with `curl /api/v1/readiness`
8. Confirm API-key auth is enabled for `/api/*` or enforced by a trusted upstream gateway
9. If gateway approvals use `/webhook/approve/{request_id}`, set `MULLU_GATEWAY_APPROVAL_SECRET` and send it via `X-Mullu-Approval-Secret`
10. If approvals are deferred, run `python -m gateway.worker` beside the gateway with PostgreSQL command ledger storage
11. Set `MULLU_TENANT_IDENTITY_BACKEND=postgresql` so channel identities resolve from durable storage
12. Set `MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY=true` so gateway startup fails closed if identity storage is unavailable
13. Set `MULLU_COMMAND_LEDGER_DB_URL` when command ledger storage uses a dedicated database URL
14. Set `MULLU_COMMAND_ANCHOR_SECRET` and `MULLU_COMMAND_ANCHOR_KEY_ID` for signed command-event batch anchors
15. Set `MULLU_REQUIRE_COMMAND_ANCHOR=true` so `gateway.worker` fails closed if anchor signing is unavailable
16. Set `MULLU_GATEWAY_APPROVAL_SECRET` for approval callbacks and deferred execution admission
17. Run `python scripts/provision_runtime_witness_secret.py --runtime-env-output .change_assurance/runtime_witness_secret.env` and set the same `MULLU_RUNTIME_WITNESS_SECRET` value in the deployed gateway runtime
18. Set `MULLU_RUNTIME_CONFORMANCE_SECRET` in the deployed gateway runtime and witness collector
19. Run `python scripts/provision_deployment_target.py --gateway-url "<deployed-gateway-url>" --expected-environment production`
20. Run `python scripts/render_gateway_ingress.py --gateway-host "<gateway-dns-host>" --apply`
21. Run `gateway.capability_worker:app` outside the gateway process for dangerous capability execution
22. Set `MULLU_CAPABILITY_WORKER_URL` and `MULLU_CAPABILITY_WORKER_SECRET` on gateway and gateway worker
23. Run `python scripts/validate_gateway_deployment_env.py --strict` before claiming pilot or production readiness
24. Run `python scripts/gateway_runtime_smoke.py` against the live gateway and capability worker before claiming runtime readiness
25. Set `MULLU_BROWSER_WORKER_URL`, `MULLU_BROWSER_WORKER_SECRET`, `MULLU_DOCUMENT_WORKER_URL`, `MULLU_DOCUMENT_WORKER_SECRET`, `MULLU_VOICE_WORKER_URL`, `MULLU_VOICE_WORKER_SECRET`, `MULLU_EMAIL_CALENDAR_WORKER_URL`, and `MULLU_EMAIL_CALENDAR_WORKER_SECRET` on gateway and gateway worker before enabling adapter-backed capabilities
26. Run `python scripts/produce_capability_adapter_live_receipts.py --strict --browser-sandbox-evidence "$MULLU_BROWSER_SANDBOX_EVIDENCE" --voice-audio-path "$MULLU_VOICE_PROBE_AUDIO" --email-calendar-connector-id gmail --email-calendar-query newer_than:1d` after browser, document, voice, and email/calendar worker dependencies and connector credentials are installed
27. Run `python scripts/collect_capability_adapter_evidence.py --strict` after browser, document, voice, and email/calendar live receipts are available
28. If adapter evidence is not closed, run `python scripts/plan_capability_adapter_closure.py --json` and resolve every generated dependency, credential, and live-receipt action before promotion
29. Run `python scripts/validate_general_agent_promotion.py --output .change_assurance/general_agent_promotion_readiness.json` to write the current promotion-readiness artifact
30. If deployment witness or public health blockers remain, run `python scripts/plan_deployment_publication_closure.py --json`
31. Run `python scripts/plan_general_agent_promotion_closure.py --json`, `python scripts/validate_general_agent_promotion_closure_plan_schema.py --strict`, and `python scripts/validate_general_agent_promotion_closure_plan.py --strict` before executing promotion closure actions
32. Run `python scripts/validate_general_agent_promotion.py --strict` before claiming production general-agent readiness

## Startup Behavior

On startup, the platform:

1. Creates the persistence store (memory, SQLite, or PostgreSQL)
2. Fails closed if `MULLU_DB_BACKEND` is not `postgresql` in pilot/production
3. Fails closed if `MULLU_API_AUTH_REQUIRED`, `MULLU_CORS_ORIGINS`, durable DB URLs, command anchors, approval secrets, runtime witness/conformance secrets, or restricted capability-worker bindings are missing in pilot/production
4. Fails closed if production PostgreSQL starts without field encryption enabled
5. Fails closed if pilot/production gateway identity storage is not persistent and available
6. Fails closed if pilot/production `gateway.worker` lacks command anchor signing material
7. Fails dangerous capability execution closed if the restricted capability worker is not configured
8. Publishes signed runtime witness state at `/gateway/witness` and `/runtime/witness`
9. Restores state from file snapshots (if `MULLU_STATE_DIR` has previous snapshots)
10. Registers all subsystems into the dependency container
11. Mounts 8 router modules (health, llm, tenant, audit, workflow, agent, data, ops)
12. Applies profile-aware API auth defaults to `/api/*` routes

On shutdown:

1. Saves budget state, audit summary, and cost analytics to file snapshots
2. Flushes metrics
3. Closes database connections

## Schema Migrations

The platform includes a built-in migration engine (`mcoi_runtime.persistence.migrations`):

- Migrations are versioned, idempotent SQL
- `schema_version` table tracks applied migrations
- 4 built-in migrations: initial schema, actor index, audit trail, cost events
- Startup fails fast if any migration fails
