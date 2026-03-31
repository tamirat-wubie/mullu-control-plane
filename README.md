# Mullu Control Plane

**Govern and verify any AI agent before it touches the real world.**

Connect your existing agents (Claude Code, OpenAI, scripts, tools), enforce policy on every action, preserve audit trails, and recover safely across restarts.

## What It Does

- **Govern** — every agent action goes through a guard chain (auth, rate-limit, budget, policy) before it runs
- **Verify** — hash-chained audit trail proves what happened, who did it, and why it was allowed
- **Replay** — deterministic replay lets you re-examine any governed execution
- **Recover** — coordination checkpoints survive restarts with governed restore (lease expiry, policy drift detection)

## Quick Start

```bash
cd mcoi
pip install -e ".[dev]"
mcoi init
```

Start the server and run the demo:

```bash
uvicorn mcoi_runtime.app.server:app --port 8000
mcoi demo
```

## Connect Your Agent

Any agent can register, request permission, and submit results through 4 HTTP calls:

```bash
# Register
curl -X POST localhost:8000/api/v1/agent/register \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "my-agent", "capabilities": ["file_read", "shell"]}'

# Request permission for an action
curl -X POST localhost:8000/api/v1/agent/action-request \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-xxx", "action_type": "shell", "target": "ls -la"}'

# Submit result
curl -X POST localhost:8000/api/v1/agent/action-result \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-xxx", "action_id": "act-000001", "outcome": "success", "result": {}}'

# Check audit trail
curl localhost:8000/api/v1/audit?action=agent.adapter.action_request
```

## What You Get

| Layer | Capability |
|-------|-----------|
| **Governance** | Guard chain, policy packs, budget enforcement, rate limiting |
| **Audit** | Hash-chain integrity, searchable by tenant/action/outcome |
| **Providers** | Anthropic, OpenAI, Gemini, Ollama, Stub (3-tier stack) |
| **Coordination** | Checkpoint/restore with lease expiry, retry caps, policy drift detection |
| **Observability** | Health v3, Prometheus metrics, Grafana dashboards, request tracing |
| **Security** | API key auth, SSRF protection, thread-safe caches, bounded queues |

## Architecture

```
mullu-control-plane/
|- mcoi/              # MCOI Runtime (Python)
|  |- mcoi_runtime/
|  |  |- app/         # FastAPI server, CLI, 9 router modules
|  |  |- core/        # Engines (governance, LLM, coordination, workflow)
|  |  |- contracts/   # Frozen dataclass contracts (160+ types)
|  |  |- adapters/    # LLM backends, filesystem, code, document
|  |  |- persistence/ # Stores (trace, snapshot, coordination, memory)
|  |  \- pilot/       # Deployment paths
|  \- tests/          # 44,780+ tests
|- maf/               # MAF Core (Rust certifying substrate)
|- schemas/           # Canonical JSON schemas
|- scripts/           # Validation, staging drill
\- .github/           # CI workflows (nightly + provider certification)
```

## Docs

- [OPERATOR_GUIDE_v0.1.md](OPERATOR_GUIDE_v0.1.md) — profiles, CLI, env vars, provider config
- [DEPLOYMENT.md](DEPLOYMENT.md) — Docker, production setup, K8s manifests
- [KNOWN_LIMITATIONS_v0.1.md](KNOWN_LIMITATIONS_v0.1.md) — documented limitations
- [SECURITY_MODEL_v0.1.md](SECURITY_MODEL_v0.1.md) — security model and boundaries
