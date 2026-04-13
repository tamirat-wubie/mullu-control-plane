# Mullu Control Plane — Production Deployment Checklist

## Pre-Deployment

- [ ] All tests pass (`python -m pytest mcoi/tests/ -q`)
- [ ] Contract guard passes (`python scripts/validate_reflective_contracts.py` → TOTAL=0)
- [ ] No hardcoded secrets in codebase (`grep -r "sk-\|password=" --include="*.py"`)
- [ ] Docker image builds cleanly (`docker build -t mullu-control-plane .`)

## Environment Variables (Required)

| Variable | Purpose | Example |
|----------|---------|---------|
| `MULLU_ENV` | Environment identifier | `production` |
| `MULLU_DB_BACKEND` | Persistence backend | `postgres` |
| `MULLU_DB_URL` | Database connection string | `postgresql://...` |
| `MULLU_ALLOW_UNKNOWN_TENANTS` | Reject unknown tenants | `false` |

## Environment Variables (LLM — at least one required)

| Variable | Provider |
|----------|----------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude) |
| `OPENAI_API_KEY` | OpenAI (GPT) |
| `GROQ_API_KEY` | Groq |
| `GOOGLE_API_KEY` | Google (Gemini) |

## Environment Variables (Gateway Channels — optional)

| Variable | Channel |
|----------|---------|
| `WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_APP_SECRET` | WhatsApp |
| `SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET` | Slack |
| `TELEGRAM_BOT_TOKEN` | Telegram |
| `DISCORD_BOT_TOKEN` + `DISCORD_PUBLIC_KEY` | Discord |

## Security Checklist

- [ ] CSP headers enabled (SecurityHeadersMiddleware with `environment=production`)
- [ ] HSTS enabled (automatic in production mode)
- [ ] Input validation middleware active
- [ ] API keys have expiration dates set
- [ ] Webhook signature verification configured per channel
- [ ] PII scanner enabled (default)
- [ ] Content safety chain enabled (default)
- [ ] `MULLU_ALLOW_UNKNOWN_TENANTS=false` in production

## Monitoring Checklist

- [ ] `/health` endpoint returns `{"status": "healthy"}`
- [ ] Prometheus metrics endpoint accessible
- [ ] Audit trail writing to persistent store (not in-memory)
- [ ] Governance decision log active
- [ ] Webhook event log active
- [ ] Provider health monitor tracking all providers

## Database

- [ ] PostgreSQL 14+ with WAL mode
- [ ] Schema migrations applied (`governance_budgets`, `governance_audit_entries`, `governance_rate_decisions`, `governance_tenant_gates`)
- [ ] Connection pooling configured
- [ ] Backup schedule in place

## Kubernetes (if applicable)

- [ ] `k8s/namespace.yaml` applied
- [ ] `k8s/mullu-api.yaml` deployed with PVC
- [ ] `k8s/postgres.yaml` deployed (or use managed DB)
- [ ] Resource limits set (CPU, memory)
- [ ] Liveness probe: `/health`
- [ ] Readiness probe: `/ready`

## Post-Deployment Verification

```bash
# API health
curl https://your-domain/health

# Gateway health
curl https://your-domain:8001/health

# Governance guard chain
curl https://your-domain/api/v1/guards

# Audit trail
curl https://your-domain/api/v1/audit/summary

# Rate limiter status
curl https://your-domain/api/v1/rate-limit/status
```

## Staged Rollout (Mandatory)

1. **Shadow mode** — Deploy alongside existing system, no live traffic
2. **Canary mode** — 5% traffic, monitor error rates and latency
3. **Gradual rollout** — 25% → 50% → 100% over 1 week
4. **Full production** — All traffic, monitoring dashboards active
