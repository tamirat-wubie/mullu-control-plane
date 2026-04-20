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

## Startup Behavior

On startup, the platform:

1. Creates the persistence store (memory, SQLite, or PostgreSQL)
2. Warns if `MULLU_DB_BACKEND=memory` in non-dev environments
3. Warns if `MULLU_CORS_ORIGINS` is empty in production
4. Fails closed if production PostgreSQL starts without field encryption enabled
5. Restores state from file snapshots (if `MULLU_STATE_DIR` has previous snapshots)
6. Registers all subsystems into the dependency container
7. Mounts 8 router modules (health, llm, tenant, audit, workflow, agent, data, ops)
8. Applies profile-aware API auth defaults to `/api/*` routes

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
