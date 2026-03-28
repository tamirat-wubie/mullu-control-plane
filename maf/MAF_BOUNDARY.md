# MAF Boundary Document

## What MAF Is

MAF (Mullu Agentic Framework) is the **certifying substrate** for the Mullu Platform. It owns the deep invariants that every runtime vertical must respect.

MAF is:
- **Small** — types and transition logic, not application behavior
- **Strict** — forbidden transitions are rejected, not logged and ignored
- **Provable** — every transition produces a receipt
- **Reusable** — usable by MCOI, future verticals, simulation runtimes, test harnesses

## What Belongs in MAF

| Category | Examples | Crate |
|----------|----------|-------|
| State types | `PolicyStatus`, `ExecutionOutcome`, lifecycle enums | maf-kernel |
| Transition logic | `StateMachineSpec`, `is_legal()`, `certify_transition()` | maf-kernel |
| Proof objects | `TransitionReceipt`, `ProofCapsule`, `CausalLineage` | maf-kernel |
| Capability classification | `EffectClass`, `TrustClass`, `CapabilityDescriptor` | maf-capability |
| Event contracts | `EventRecord`, `ObligationRecord`, lifecycle states | maf-event |
| Governance DSL | `PolicyRule`, `PolicyBundle`, `PolicyEvaluationTrace` | maf-governance |
| Supervisor contracts | `SupervisorTick`, `LivelockRecord`, `CheckpointStatus` | maf-supervisor |
| Operational reasoning | Simulation, utility, benchmark contracts | maf-ops |
| Orchestration types | Job, workflow, goal, function, role contracts | maf-orchestration |
| Learning contracts | Decision learning, provider routing, meta-reasoning | maf-learning |

## What Must Stay in MCOI

| Category | Examples | Why |
|----------|----------|-----|
| API endpoints | FastAPI routes, request/response models | Product-facing |
| Adapters | HTTP, SMTP, LLM providers, browser | Provider-specific |
| Persistence | SQLite, PostgreSQL, InMemoryStore | Implementation detail |
| App wiring | server.py, middleware, bootstrap | Deployment-specific |
| Tenant behavior | Budgets, quotas, isolation | Business logic |
| Operator surfaces | CLI, console, dashboards | Product UX |
| Workflow engines | Execution engines, pipeline runners | Runtime behavior |

## Decision Rule

When deciding where a type or function belongs, ask:

1. **Is it universal across future runtimes?** → MAF
2. **Is it invariant (not configurable per deployment)?** → MAF
3. **Would duplication create drift risk?** → MAF
4. **Could another runtime use it without importing MCOI?** → MAF
5. **Does it describe legality/proof, not execution plumbing?** → MAF

If 4+ answers are "yes" → MAF. Otherwise → MCOI.

## Architecture

```
MAF (Rust substrate)
├── maf-kernel        — state, transitions, proofs, receipts
├── maf-capability    — capability classification
├── maf-agent         — agent abstractions
├── maf-event         — event spine, obligations
├── maf-governance    — policy DSL, rules, bundles
├── maf-supervisor    — supervisor tick lifecycle
├── maf-ops           — simulation, utility, benchmarks
├── maf-orchestration — jobs, workflows, goals, roles
└── maf-learning      — decision learning, routing, meta-reasoning

MCOI (Python runtime)
├── contracts/        — Python mirrors of MAF types (serde-compatible)
├── core/             — engines, managers, runtime behavior
├── adapters/         — LLM, HTTP, streaming connectors
├── app/              — FastAPI server, routers, middleware
├── persistence/      — stores, migrations, state snapshots
└── pilot/            — deployment profiles, domain packs
```

## Key Invariant

**MAF should never import or depend on MCOI.** The dependency flows one way:

```
MCOI → MAF (via serde-compatible types)
```

MCOI's Python contracts mirror MAF's Rust types. They are kept in sync via:
- Matching enum variant names (snake_case serialization)
- JSON schema compatibility tests
- Round-trip serialization tests in both languages
