# Mullu — Governed Autonomous Agent Platform

**Every agent action is auditable, budget-controlled, policy-enforced, and approval-gated.**

Mullu is a governed operational intelligence platform. Users interact via messaging channels (WhatsApp, Telegram, Slack, Discord, Web). The agent executes real-world tasks — email, payments, document generation, data analysis — under deterministic governance: 7-guard chain, hash-chain audit trails, financial spend budgets, and skill boundary enforcement.

## Quick Start

```bash
# Setup
python -m installer.cli init

# Start (3 services: PostgreSQL + API + Gateway)
docker-compose up

# Gateway health
curl http://localhost:8001/health

# API health
curl http://localhost:8000/health
```

## What It Does

```
User (WhatsApp/Telegram/Slack/Discord/Web)
  → Channel Adapter (normalize + verify signature)
  → Gateway Router (resolve tenant + risk classify + approval gate)
  → GovernedSession (RBAC → content safety → budget → LLM → PII redaction → audit → proof)
  → Response
```

Every message flows through the full governance pipeline. No bypass path.

## Platform Capabilities

### Governance Engine (45,300+ tests)

| Capability | What |
|---|---|
| **7-Guard Chain** | API key → JWT → tenant → gating → RBAC → content safety → rate limit → budget |
| **GovernedSession** | `session = platform.connect(identity_id, tenant_id)` then `session.llm("prompt")` |
| **ProofBridge** | Every governance decision produces a cryptographic TransitionReceipt |
| **Content Safety** | 6 prompt injection patterns + Unicode normalization + base64 decode |
| **PII Scanner** | 7 patterns (email, phone, SSN, credit card, IP, API key, password) |
| **Field Encryption** | AES-256-GCM on audit store detail fields |
| **RBAC** | 9 roles (admin → financial_admin) + permission rules |

### 10 LLM Providers

| Provider | Free Tier | Best For |
|---|---|---|
| Anthropic (Claude) | No | Complex reasoning |
| OpenAI (GPT) | No | General purpose |
| Groq (Llama 4) | Yes | Fast inference, simple queries |
| Google Gemini | 1K/day free | Balanced |
| DeepSeek (V3.2) | $5 credit | Best price-performance |
| xAI Grok | $25 credit | Real-time X/Twitter data |
| Mistral | Limited | Cheapest ($0.02/M) |
| OpenRouter | Community | Multi-provider routing |
| Ollama | Self-hosted | Local/private |
| Stub | Always | Testing |

**Adaptive reasoning** routes simple queries to free providers, complex tasks to premium models.

### Channel Gateway (5 channels)

| Channel | Features |
|---|---|
| WhatsApp | Cloud API, signature verification, media handling |
| Telegram | Bot API, inline keyboards for approval prompts |
| Slack | Events API, thread tracking, HMAC verification |
| Discord | Interactions, Ed25519 verification, slash commands |
| Web | WebSocket chat, session management |

Plus: approval routing (LOW/MEDIUM/HIGH risk), session manager with TTL, skill dispatcher for financial intents, multi-agent handoff with loop detection.

### Financial Operations

| Capability | What |
|---|---|
| **Decimal-Safe Currency** | Never float — ISO 4217, banker's rounding |
| **Spend Budgets** | Per-tx/daily/weekly/monthly limits with auto-reset |
| **Transaction State Machine** | 10 states: CREATED → SETTLED → REFUNDED |
| **Idempotency** | Same request = same result (no duplicate payments) |
| **Governed Payments** | Budget → approval → idempotency → Stripe → settlement → ledger → proof |
| **Compliance Export** | Audit packages with integrity hashes for external review |

### Creative Skills

| Skill | What |
|---|---|
| Document Generation | Invoice, memo, receipt, summary templates + LLM wrapping |
| Data Analysis | CSV stats, insights, numeric/text detection |
| Image Generation | DALL-E integration with content safety + cost tracking |
| Translation | 20 languages including Amharic, Swahili, Yoruba |
| Summarization | Compression ratio tracking |

### Enterprise Skills

| Skill | What |
|---|---|
| **RAG Knowledge Base** | Tenant-scoped document ingestion → chunking → embedding → retrieval → LLM prompt injection |
| **Notification System** | Slack/email/webhook alerts on governance events (approval, budget, payment, security) |
| **Task Scheduler** | Cron-based governed execution with concurrency prevention + failure tracking |

### MCP Server

External agents (Claude Code, Cursor, etc.) connect to Mullu as a governed tool provider:

```json
{"method": "tools/call", "params": {"name": "mullu_llm", "arguments": {"prompt": "What is 2+2?"}}}
```

6 governed tools: `mullu_llm`, `mullu_query`, `mullu_execute`, `mullu_balance`, `mullu_transactions`, `mullu_pay`.

## Architecture

```
mullu-control-plane/
├── mcoi/                   # MCOI Runtime (Python, 45,300+ tests)
│   ├── mcoi_runtime/
│   │   ├── app/            # FastAPI server, 19 routers, CLI
│   │   ├── core/           # 380+ engines (governance, LLM, coordination)
│   │   ├── contracts/      # 160+ frozen dataclass types
│   │   ├── adapters/       # 10 LLM backends, shell, browser, HTTP
│   │   ├── persistence/    # PostgreSQL + SQLite + memory stores
│   │   ├── mcp/            # MCP server (tool provider for external agents)
│   │   └── pilot/          # Deployment profiles
│   └── tests/
├── gateway/                # Channel Gateway (WhatsApp, Telegram, Slack, Discord, Web)
│   ├── channels/           # 5 channel adapters
│   ├── router.py           # Unified message routing
│   ├── approval.py         # Risk classification + approval lifecycle
│   ├── session.py          # Conversation context management
│   ├── skill_dispatch.py   # Financial intent detection
│   ├── handoff.py          # Multi-agent handoff with loop detection
│   └── server.py           # FastAPI webhook server (port 8001)
├── skills/
│   ├── financial/          # Currency, budgets, Stripe, payments, compliance
│   ├── creative/           # Documents, data analysis, images, translation
│   └── enterprise/         # RAG, notifications, scheduler
├── installer/              # mullusi init interactive setup wizard
├── maf/                    # MAF Rust certifying substrate
├── schemas/                # 17 canonical JSON schemas
├── k8s/                    # Kubernetes manifests (security hardened)
└── docker-compose.yml      # 3-service deployment (postgres + API + gateway)
```

### Governed Evolution

System changes are certified before production use:

```bash
python scripts/certify_change.py --base HEAD --head current --strict --approval-id local-approval --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md
```

The command emits `.change_assurance/change_command.json`,
`.change_assurance/blast_radius.json`, `.change_assurance/invariant_report.json`,
`.change_assurance/replay_report.json`, and
`.change_assurance/release_certificate.json`. See
`docs/33_governed_evolution.md`.

### Accepted Risk Closure

Unresolved verification gaps can be held open only through bounded accepted-risk
records with owner, approver, case, expiry, review obligation, and evidence.
See `docs/34_accepted_risk_closure.md`.

### Compensation Assurance

Rollback and compensation actions are treated as evidence-bearing recoveries:
they must be approved, dispatched through an injected capability, observed,
verified, reconciled, and graph-anchored before recovery can be claimed. See
`docs/35_compensation_assurance.md`.

### Closure Memory Promotion

Verified execution closures, explicit accepted-risk closures, failure records,
and successful compensation outcomes can be admitted into append-only episodic
memory without skipping into semantic or procedural memory. See
`docs/36_closure_memory_promotion.md`.

### Terminal Closure Certificate

Effect-bearing commands can be capped with a final certificate that names exactly
one disposition: committed, compensated, accepted risk, or requires review. See
`docs/37_terminal_closure_certificate.md`.

### Closure Learning Admission

Terminal closure certificates and episodic closure memory now pass through an
explicit learning admission gate before they can be used as semantic or
procedural planning knowledge. See `docs/38_closure_learning_admission.md`.

### Procedural Memory Admission

Runbook admission now requires an explicit admitted learning decision in
addition to successful execution, passing verification, and replay integrity.
The learning admission id is carried in runbook provenance.

### Semantic Memory Admission

Generalized knowledge now has a versioned semantic memory write gate:
`KnowledgeRecord` entries require an admitted learning decision, source refs,
and evidence before storage. Updates append new versions.

## Deployment

```bash
# Interactive setup
python -m installer.cli init

# Docker (3 services)
docker-compose up

# Kubernetes
kubectl apply -f k8s/
```

**Security hardened:** restart policies, resource limits, network isolation, securityContext (runAsNonRoot), NetworkPolicy, PodDisruptionBudget.

## Repository Status

The public repository surface is bounded by a versioned status witness:
[STATUS.md](STATUS.md). That witness names the audited branch head, release
alignment, CI gates, governance checks, and known reflection gaps.

## Docs

- [OPERATOR_GUIDE_v0.1.md](OPERATOR_GUIDE_v0.1.md) — profiles, CLI, env vars
- [DEPLOYMENT.md](DEPLOYMENT.md) — Docker, K8s, production setup
- [SECURITY_MODEL_v0.1.md](SECURITY_MODEL_v0.1.md) — security model, 5 DCA audits
- [KNOWN_LIMITATIONS_v0.1.md](KNOWN_LIMITATIONS_v0.1.md) — documented limitations
- [RUNBOOK.md](RUNBOOK.md) — operational procedures

## Tests

```bash
cd mcoi && python -m pytest tests/ -q          # 45,300+ tests
cd .. && python -m pytest tests/ -q             # Gateway + financial + creative + enterprise
```

## License

See [LICENSE](LICENSE).
