# Mullu — Governed Autonomous Agent Platform

**Every agent action is auditable, budget-controlled, policy-enforced, and approval-gated.**

Mullu is a governed operational intelligence platform. Users interact via messaging channels (WhatsApp, Telegram, Slack, Discord, Web). The agent executes real-world tasks — email, payments, document generation, data analysis — under deterministic governance: 8-guard chain, hash-chain audit trails, financial spend budgets, and skill boundary enforcement.

The next operational-intelligence extension is specified in [`docs/62_governed_operational_intelligence.md`](docs/62_governed_operational_intelligence.md): world-state graph, goal compiler, causal simulator, capability forge, worker mesh, maturity levels, policy prover, memory lattice, trust ledger, and domain operating packs.

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

### Governance Engine (47,800+ tests)

| Capability | What |
|---|---|
| **8-Guard Chain** | API key → JWT → tenant → gating → RBAC → content safety → rate limit → budget. Order, fail-closed semantics, and known gaps in [`docs/GOVERNANCE_GUARD_CHAIN.md`](docs/GOVERNANCE_GUARD_CHAIN.md). |
| **GovernedSession** | `session = platform.connect(identity_id, tenant_id)` then `session.llm("prompt")` |
| **ProofBridge** | Governance decisions on `/api/v1/*` produce a deterministic TransitionReceipt via middleware. Coverage and known gaps documented in [`docs/MAF_RECEIPT_COVERAGE.md`](docs/MAF_RECEIPT_COVERAGE.md). |
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

### MUSIA — Universal Symbolic Causal Intelligence (v4.18)

A second governance layer added in v4.x: 25 universal constructs across 5 tiers, the Φ_gov core operator, and the SCCCE cognition cycle. Plugs into the existing 8-Guard Chain via the `Φ_gov ↔ GovernanceGuardChain` bridge so a single chain instance gates writes AND domain runs.

| Capability | What |
|---|---|
| **25 Constructs** | 5 tiers (Foundational, Structural, Coordination, Governance, Cognitive); Tier 1 directly POSTable, Tiers 2–5 cycle-derived |
| **Mfidel Substrate** | 34×8 atomic encoding grid; 269 atoms with 3 known-empty col-8 slots |
| **Φ_gov + Φ_agent** | Governance core operator with 6-level filter stack (L0 Physical/Logical → L5 Optimization), 4-state ProofState |
| **6 Domain Adapters** | software_dev, business_process, scientific_research, manufacturing, healthcare, education — uniform UCJA L0–L9 pipeline |
| **Chain Bridge** | Existing platform `GovernanceGuardChain` plugs into MUSIA's `external_validators` slot (v4.15 writes, v4.16 domain runs) |
| **Observability** | `/musia/governance/stats` admin endpoint — per-(surface, verdict, tenant, guard) counters + 50-event rejection ring |
| **Multi-Tenant** | Per-tenant registry + quota + sliding-window rate limit + persistent state + run audit trail; opt-in `max_tenants` cap (v4.18) |

HTTP surface: `/constructs/*`, `/domains/<six>/process`, `/cognition/*`, `/ucja/*`, `/mfidel/*`, `/musia/tenants/*`, `/musia/governance/*`. Chain runs in microseconds (5–16μs typical, 5-guard chain p99 ≤ 41μs — see [`tests/test_v4_17_chain_latency_bench.py`](mcoi/tests/test_v4_17_chain_latency_bench.py)).

Per-release detail in `RELEASE_NOTES_v4.0.0.md` through `RELEASE_NOTES_v4.26.0.md` at repo root. v4.26.0 closes audit-found authorization gaps in the MUSIA layer (F13/F14/F16) and adds a route-coverage CI gate.

### MCP Server

External agents (Claude Code, Cursor, etc.) connect to Mullu as a governed tool provider:

```json
{"method": "tools/call", "params": {"name": "mullu_llm", "arguments": {"prompt": "What is 2+2?"}}}
```

6 governed tools: `mullu_llm`, `mullu_query`, `mullu_execute`, `mullu_balance`, `mullu_transactions`, `mullu_pay`.

## Architecture

```
mullu-control-plane/
├── mcoi/                   # MCOI Runtime (Python, 47,800+ tests)
│   ├── mcoi_runtime/
│   │   ├── app/            # FastAPI server, 35 routers (legacy + MUSIA), CLI
│   │   ├── substrate/      # MUSIA: Mfidel grid + 25-construct framework + Φ_gov
│   │   ├── cognition/      # MUSIA: 15-step SCCCE cycle (symbol field, tension, convergence)
│   │   ├── ucja/           # MUSIA: L0–L9 execution pipeline
│   │   ├── domain_adapters/ # MUSIA: 6 domain adapters (software_dev, business_process, scientific_research, manufacturing, healthcare, education)
│   │   ├── migration/      # MUSIA: bulk proof v1→v2 migration runner
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
├── maf/                    # MAF Rust crate — receipt-shape parity with Python contracts. NOT currently in the request path: Python does not call into Rust today (no PyO3 bindings, maf-cli is a scaffold). See docs/MAF_RECEIPT_COVERAGE.md for the honest baseline of what is and isn't certified.
├── schemas/                # 23 canonical JSON schemas (incl. MUSIA universal_construct)
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

### Pilot Proof Slice

Pilot readiness can be checked without live providers by emitting a local
proof-slice witness:

```bash
python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json
```

The proof slice sends one deterministic tenant-scoped web message through the
gateway router, command ledger, causal closure kernel, terminal certificate,
closure memory promotion, and learning admission path. CI runs the proof-slice
tests and emits the witness in the gateway closure job.

### Accepted Risk Closure

Unresolved verification gaps can be held open only through bounded accepted-risk
records with owner, approver, case, expiry, review obligation, and evidence.
See `docs/34_accepted_risk_closure.md`.

### Authority-Obligation Mesh

Gateway authority is responsibility-certified before and after closure:
commands bind ownership, approval chains, separation of duty, review
obligations, expiry, escalation, and runtime witness counts. Operator read
models expose ownership, policy, approval-chain, obligation, and escalation
state with bounded filters. External directory sync is specified in
`docs/54_authority_directory_sync.md`.

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
cd mcoi && python -m pytest tests/ -q          # 47,800+ tests
cd .. && python -m pytest tests/ -q             # Gateway + financial + creative + enterprise
```

## License

See [LICENSE](LICENSE).
