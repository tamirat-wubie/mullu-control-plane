# Mullu Platform

Mullu Platform is the umbrella repository for the shared substrate and the
computer-operations vertical.

- **MAF Core** is the general agentic substrate.
- **MCOI Runtime** is the computer operating intelligence vertical.
- **Mullu Control Plane** is the operator-facing gateway, status, approvals, and
  trace surface.
- **Shared Contracts** are the canonical schemas and invariants used by both
  runtimes.

The repository keeps the substrate and the computer-operations vertical in a hard
split. Shared meaning lives once in `docs/` and `schemas/`.

## Repository Tree

```text
mullu-platform/
|- README.md
|- LICENSE
|- .gitignore
|- docs/
|- schemas/
|- maf/
|  \- rust/
|- mcoi/
|  |- pyproject.toml
|  |- examples/
|  |- mcoi_runtime/
|  |  |- contracts/
|  |  |- core/
|  |  |- adapters/
|  |  |- app/
|  |  |- persistence/
|  |  \- pilot/
|  \- tests/
|- integration/
|- scripts/
|- tests/
\- .github/
```

## Current State (v3.10.1)

**Stage: production-candidate in final activation**

- **MCOI Runtime** — governed AI operating system with 162 API endpoints
  across 8 router modules, multi-tenant budget enforcement, hash-chain audit
  trails, LLM orchestration (Anthropic/OpenAI/stub), agent workflows, cost
  analytics, and full governance guard chain. 44,500+ Python tests.
- **MAF Core** — certifying Rust substrate with transition receipts, proof
  capsules, causal lineage, benchmark gates, and 180 tests.
- **Shared Contracts** — canonical schemas and docs defining cross-runtime
  meaning, with serde-compatible Python↔Rust proof objects.

### Key Capabilities

| Capability | Description |
|------------|-------------|
| LLM Governance | Budget enforcement, cost tracking, circuit breakers |
| Multi-Tenant | Isolated budgets, ledgers, conversations per tenant |
| Audit Trail | Hash-chain integrity, query by action/tenant/outcome |
| Agent Orchestration | Workflows, chains, tool-augmented agents, A/B testing |
| Observability | Health v3, Prometheus metrics, Grafana dashboards, tracing |
| Security | API key auth, CORS lockdown, SSRF protection, read timeouts |
| MAF Proof Substrate | Transition receipts, guard verdicts, causal lineage |
| Operational Certification | Persistence lifecycle, concurrency stress, staging drill |

## Quick Start

```bash
cd mcoi
pip install -e ".[dev]"
uvicorn mcoi_runtime.app.server:app --reload
curl http://localhost:8000/health
```

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Docker, production setup, and environment variables.

## Practical Notes

- The CLI entrypoint is `mcoi`.
- Portable example requests live under `mcoi/examples/`.
- Runtime limitations are tracked in `KNOWN_LIMITATIONS_v0.1.md`.
- Deployment profiles and env vars are documented in `DEPLOYMENT.md`.
