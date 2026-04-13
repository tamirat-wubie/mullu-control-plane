# Mullu Control Plane — Quickstart Guide

Get the governed autonomous agent platform running in 5 minutes.

## Prerequisites

- Python 3.12+ (3.13 recommended)
- pip
- (Optional) Docker for PostgreSQL
- (Optional) Channel API credentials (WhatsApp, Slack, Telegram, Discord)

## 1. Install

```bash
cd mullu-control-plane
pip install -e ./mcoi
```

## 2. Run Tests

```bash
cd mcoi
python -m pytest tests/ -q
```

Expected: 46,000+ tests pass.

## 3. Start the API Server

```bash
# Minimal (in-memory stores, no LLM)
MULLU_ENV=local_dev uvicorn mcoi_runtime.app.server:app --port 8000

# With LLM provider
ANTHROPIC_API_KEY=sk-... uvicorn mcoi_runtime.app.server:app --port 8000
```

## 4. Start the Gateway Server

```bash
# Minimal (web chat only)
uvicorn gateway.server:app --port 8001
```

## 5. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Gateway health
curl http://localhost:8001/health

# Web chat message
curl -X POST http://localhost:8001/webhook/web \
  -H "Content-Type: application/json" \
  -d '{"text": "What is 2+2?", "sender_id": "test-user"}'
```

## 6. Use the SDK (GovernedSession)

```python
from mcoi_runtime.core.governed_session import Platform

platform = Platform.from_env()
session = platform.connect(identity_id="user1", tenant_id="t1")

result = session.llm("What is the capital of France?")
print(result.content)

report = session.close()
print(f"Operations: {report.operations}, Cost: ${report.total_cost:.4f}")
```

## 7. Configure Channels

Set environment variables for each channel:

```bash
# WhatsApp
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_APP_SECRET=...

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...

# Telegram
TELEGRAM_BOT_TOKEN=...

# Discord
DISCORD_BOT_TOKEN=...
DISCORD_PUBLIC_KEY=...
```

## 8. Production Configuration

```bash
# Database (PostgreSQL instead of in-memory)
MULLU_DB_BACKEND=postgres
MULLU_DB_URL=postgresql://user:pass@host:5432/mullu

# Environment
MULLU_ENV=production

# Tenant gating (reject unknown tenants in production)
MULLU_ALLOW_UNKNOWN_TENANTS=false
```

## Next Steps

- Read `docs/PHI_CANONICAL_SPEC.md` for the full architecture
- Read `docs/00_platform_overview.md` for the platform structure
- Read `docs/DEPLOYMENT.md` for production deployment
