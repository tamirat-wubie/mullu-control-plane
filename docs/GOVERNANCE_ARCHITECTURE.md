# Mullu Governance Package — Architecture Reference

**Audience:** contributors adding or modifying governance code; operators understanding what runs at request time
**Status:** authoritative as of v4.42.0 (audit F7 closed)
**Companion docs:** [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md) (operational), [`MAF_RECEIPT_COVERAGE.md`](MAF_RECEIPT_COVERAGE.md) (receipt invariant)

This document is the canonical reference for the `mcoi_runtime/governance/` package — what lives there, what invariants apply, and how to extend it without breaking the audit-grade properties the v4.26–v4.42 series established.

---

## The package at a glance

```
mcoi_runtime/governance/
├── __init__.py
├── auth/
│   ├── jwt.py              — JWT/OIDC validation (HS*, RS*, JWKS)
│   └── api_key.py          — API key minting + verification
├── guards/
│   ├── chain.py            — GovernanceGuardChain + factory functions
│   ├── rate_limit.py       — token-bucket rate limiter (atomic SQL)
│   ├── budget.py           — per-tenant cost/call budget (atomic SQL)
│   ├── tenant_gating.py    — per-tenant active/suspended/disabled status
│   ├── access.py           — RBAC engine (identities, roles, permissions, delegations)
│   └── content_safety.py   — prompt injection + output safety filters
├── audit/
│   ├── trail.py            — append-only hash chain audit log
│   ├── anchor.py           — checkpoint anchor for prune-resilient verification
│   ├── export.py           — JSONL exporter with chain integrity preservation
│   └── decision_log.py     — per-request governance decision record
├── network/
│   ├── ssrf.py             — unified SSRF policy (cloud metadata blocklists, DNS resolution)
│   └── webhook.py          — outbound webhook delivery with SSRF re-check
├── policy/
│   ├── engine.py           — policy decision engine (status, reason, decision factory)
│   ├── enforcement.py      — privilege elevation, session lifecycle, revocation
│   ├── provider.py         — per-provider policy (HTTP, SMTP, process)
│   ├── sandbox.py          — policy simulation sandbox
│   ├── simulation.py       — policy diff + adoption analysis
│   ├── versioning.py       — policy version registry + shadow evaluation
│   └── shell.py            — shell command policy
└── metrics.py              — governance metrics aggregation (Prometheus exposition)
```

22 modules, 6 sub-packages, ~5,000 LoC of governance logic. Each module has zero internal coupling to the others except for three intentional edges:

- `network/webhook.py` → `network/ssrf.py` (delivery-time re-check uses the shared SSRF policy)
- `audit/export.py` → `audit/trail.py` (exporter reads the trail's entries)
- `policy/versioning.py` → `policy/engine.py` (versioning wraps engine)

That's the entire intra-package dependency graph. Every other module is a leaf.

---

## What lives outside `governance/`

The audit surface is `governance/`. These adjacent things stay in `core/`:

- **Orchestrators** (`governed_session.py`, `governed_dispatcher.py`, `governed_tool_use.py`, `governed_capability_registry.py`) — they *consume* governance but don't enforce policy themselves. Per the F7 plan, they stay where they are.
- **Domain-specific governance variants** (`adapter_governance.py` and similar) — they belong with their respective adapter, not in the central audit surface.
- **Higher-order governance concepts** (`constitutional_governance.py`, `data_governance.py`, `federated_*.py`) — separate concerns, larger reorg if ever needed.
- **Integration shims** (`*_integration.py`) — tied to the orchestrator they integrate; same scoping reason.

If you're not sure whether a module belongs in `governance/`, ask: **does it enforce, audit, or carry policy at request time?** If yes, it goes in `governance/`. If it merely orchestrates around governance, it stays in `core/`.

---

## The five architectural invariants

These are non-negotiable properties of the governance surface. Every PR that touches `governance/` must preserve them.

### 1. Atomic SQL doctrine

Every persistent governance write must be a single atomic SQL statement that returns the post-state, not a read-then-write sequence.

```python
# WRONG — two replicas race the same read
budget = self.load(tenant_id)
new_spent = budget.spent + cost
if new_spent > budget.max_cost:
    return False
self.save(LLMBudget(spent=new_spent, ...))   # both replicas may write the same value

# RIGHT — one atomic UPDATE; the WHERE clause is the gate
cur.execute(
    "UPDATE governance_budgets SET spent = spent + %s, calls_made = calls_made + 1 "
    "WHERE tenant_id = %s AND spent + %s <= max_cost "
    "RETURNING budget_id, tenant_id, max_cost, spent, ...",
    (cost, tenant_id, cost),
)
row = cur.fetchone()
return row is not None
```

This pattern was established in v4.27 (`tenant_budget.try_record_spend`) and replicated in v4.29 (`rate_limiter.try_consume`), v4.30 (`hash_chain.try_append`), and v4.31 (`audit_trail.try_append`). The DB is the source of truth; in-memory caches are out of the write path.

Why it matters: without atomic SQL, two replicas can both observe `spent=$5`, both compute `$5 + $1`, both UPDATE to `$6`. Real spend `$7`, stored `$6`. The hard limit becomes soft by N replicas × in-flight requests.

### 2. Identity preservation

`isinstance` checks, identity comparisons, and frame-based introspection across the package boundary must keep working. A class imported via `mcoi_runtime.governance.auth.jwt.JWTAuthenticator` is the same Python object as it was at any prior import point.

This is why the v4.38–v4.42 reorganization went through 4 phases instead of one big-bang: each phase preserved identity, so callers could migrate incrementally without breaking type checks.

### 3. Fail-closed defaults

Every authentication-affecting flag defaults to the safe posture. Explicit opt-out is required to relax. This is the JWT hardening doctrine from v4.33:

```python
@dataclass(frozen=True, slots=True)
class OIDCConfig:
    require_subject: bool = True
    require_tenant_claim: bool = True
    require_iat_not_in_future: bool = True
    require_https_jwks: bool = True
```

Same pattern for env binding (v4.35): `MULLU_ENV` unset + `MULLU_ENV_REQUIRED=true` is a hard `EnvBindingError` at boot. No silent fallback to `local_dev`.

If you add a new auth-affecting flag, **default it to the strict posture**. Operators who genuinely need the relaxed mode opt in explicitly; misconfiguration produces a hard failure, not a silent permission grant.

### 4. Bounded error messages

Error strings reaching the request response must not contain user-controlled input or backend implementation details. The audit-grade pattern:

```python
def _bounded_tenant_mismatch_reason() -> str:
    return "tenant mismatch"   # bounded — no tenant_id, no internal state

def _bounded_store_failure(exc: Exception) -> str:
    return type(exc).__name__   # bounded — no exc.args content
```

This is why every audit-grade error string in `governance/` is a constant or a tightly-controlled format. Tests assert exact strings to catch drift.

### 5. Connection-pool-safe storage

Storage backends (`AuditStore`, `BudgetStore`, `RateLimitStore`, `TenantGatingStore`) implement an optional `try_*` primitive that the dispatcher uses when the store overrides it. The dispatcher's MRO check distinguishes between stores that opt into atomic semantics vs stores that don't:

```python
class BudgetStore:
    def try_record_spend(self, tenant_id, cost, tokens=0):
        return None   # base class signals "no atomic primitive"

class PostgresBudgetStore(_PostgresBase, BudgetStore):
    def try_record_spend(self, tenant_id, cost, tokens=0):
        # Atomic UPDATE … RETURNING
        ...   # returns LLMBudget|None
```

The manager checks `BudgetStore.try_record_spend in type(store).__mro__` to decide whether to delegate or fall back to the legacy read-modify-write path.

This pattern lets the connection-pooled stores (v4.36/v4.37) use the pool path safely: each operation acquires its own connection, the atomic SQL handles concurrency at the DB level, no Python-side global lock is needed.

---

## Adding a new governance module

If you're contributing a new `governance/<subpkg>/<name>.py`:

### 1. Pick the right sub-package

| Concern | Sub-package |
|---|---|
| Authentication (token validation, key verification) | `auth/` |
| Per-request policy enforcement (rate limit, budget, gating, RBAC, content safety) | `guards/` |
| Persistent audit record + verification | `audit/` |
| Network egress (SSRF, webhook delivery) | `network/` |
| Policy definition / enforcement engines | `policy/` |
| Cross-cutting metrics | top-level `metrics.py` |

If your module doesn't fit any of these, the package layout itself should be revisited — file an issue rather than inventing a 7th sub-package.

### 2. Follow the import-graph minimality rule

Don't import other governance modules unless behavior actually requires it. Three intentional edges exist (listed above). Adding more increases the discoverability cost: contributors reading one module need to understand more.

If you find yourself wanting to import `governance.audit.trail` from `governance.guards.budget`, check whether the audit recording can happen at the orchestrator level (in `core/governed_session.py`) instead. Usually the answer is yes.

### 3. Public API + `__all__` discipline

Each module's docstring documents its public API. The `__all__` list (when present) is the contract. Underscore-prefixed names are private and not part of the package surface — callers reaching into them depend on internal structure and accept the breakage cost when internals change.

### 4. Tests live in `mcoi/tests/test_<short_name>.py`

Test file naming follows the implementation file's logical name, not its package path:
- `governance/auth/jwt.py` → `tests/test_jwt_auth.py`
- `governance/guards/chain.py` → `tests/test_governance_guard.py`

This is because tests pre-date the F7 reorg. New tests can use either convention; consistency within a module wins.

### 5. Audit-fracture test naming

If your work closes a numbered audit fracture, the test file is `tests/test_v<X>_<Y>_<short_name>.py` — e.g. `test_v4_27_atomic_budget.py`, `test_v4_33_jwt_hardening.py`. This makes the audit-fracture lineage discoverable from the test tree.

---

## How to find what enforces what

If you're asking "what code rejects a request with `tenant mismatch`?" — the workflow:

1. Search for the literal string in `governance/` (it lives in `_bounded_tenant_mismatch_reason()` in `governance/guards/chain.py`)
2. Find the callsites (two: `create_jwt_guard` and `create_api_key_guard`, both in `chain.py`)
3. Read the test file for the audit fracture it closes (`test_v4_35_env_tenant_binding.py` for F6)

The audit-grade patterns are deliberately small and named, so this search-by-string workflow is reliable.

For Prometheus metric names — they're declared in `governance/metrics.py` and emitted from the middleware and various guards. The `PRODUCTION_DEPLOYMENT.md` lists the canonical set.

For error codes operators see in production logs — `PRODUCTION_DEPLOYMENT.md` has the complete reference, mapped to the audit-grade rejection that produced them.

---

## What `governance/` does NOT do

- **It doesn't orchestrate sessions.** That's `core/governed_session.py`.
- **It doesn't dispatch work to capabilities.** That's `core/governed_dispatcher.py`.
- **It doesn't define what data tenants can see.** RBAC is in `governance/guards/access.py`, but the tenancy model + tenant directory live elsewhere.
- **It doesn't talk to LLM providers.** That's `core/llm_*.py`.
- **It doesn't emit telemetry to specific backends.** Metrics are in-process; export is a separate concern.

If you find yourself wanting one of these things in `governance/`, the answer is probably "no, that belongs in `core/` or its own subsystem." The audit surface should stay focused.

---

## Stability commitments

The post-F7 file layout is stable. We won't reorganize it again without a published plan, a deprecation period, and a multi-phase migration like the F7 sequence.

What we MAY change in minor releases:
- Adding new modules (with the tests + naming above)
- Adding new public functions / classes to existing modules
- Adding new flags to existing configs (with safe defaults — invariant 3)

What we WON'T change without a major version bump:
- File locations
- Public API signatures
- Default flag values that affect security posture
- Atomic SQL contracts (every `try_*` primitive's return shape is part of the contract)

---

## Audit roadmap status (as of v4.42.0)

```
✅ F2  atomic budget                    — v4.27.0
✅ F3  audit checkpoint anchor          — v4.28.0
✅ F4  atomic audit append              — v4.31.0
✅ F5  env binding                      — v4.35.0
✅ F6  tenant binding                   — v4.35.0
✅ F7  governance package reorg         — v4.38 → v4.39 → v4.41 → v4.42
✅ F9  webhook SSRF                     — v4.32.0
✅ F10 DNS rebinding                    — v4.32.0
✅ F11 atomic rate limit                — v4.29.0 + v4.34.0
✅ F12 connection pool                  — v4.36.0 + v4.37.0
✅ F15 atomic hash chain                — v4.30.0 + v4.40.0
✅ F16 musia_auth wiring                — v4.26.0
✅ JWT hardening                        — v4.33.0
⏳ F8  MAF substrate disconnect         — PyO3 bridge (multi-week)
```

16 of 17 audit fractures closed. The remaining one (F8) is multi-week infrastructure work outside the contained-fracture pattern.

If a future audit identifies a 18th fracture, this document gets a new section. The five invariants above are the durable contract; specific fracture closures are the changelog.
