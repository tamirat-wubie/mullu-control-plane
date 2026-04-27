# Mullu Platform v4.3.0 — MUSIA Runtime (Multi-Tenant Isolation)

**Release date:** TBD
**Codename:** Boundary
**Migration required:** No (additive — `default` tenant preserves v4.2 behavior)

---

## What this release is

v4.2.0 shipped governed HTTP writes against a process-global construct
registry. v4.3.0 makes that registry multi-tenant: every request scopes
to a tenant via the `X-Tenant-ID` header, and constructs in one tenant
are structurally invisible to other tenants.

This is the structural enforcement of the Boundary construct at the
runtime level: each tenant *is* a Boundary, and the registry now honors
that.

---

## What is new in v4.3.0

### `TenantedRegistryStore`

New module: [substrate/registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py).

Thread-safe map of `tenant_id` → `TenantState`, where each `TenantState`
carries:
- A private `DependencyGraph` (constructs, dependents)
- A private `PhiAgentFilter` (per-tenant policy)

Get-or-create semantics: any request for an unknown tenant creates fresh
state. Production deployments with explicit onboarding flows can override
this in middleware.

Module-level singleton `STORE` is the runtime instance; tests use
`STORE.reset_all()` for isolation.

### `X-Tenant-ID` header on all `/constructs/*` and `/cognition/*` endpoints

All MUSIA endpoints now accept an `X-Tenant-ID` header:

```
POST /constructs/state HTTP/1.1
X-Tenant-ID: acme-corp
Content-Type: application/json
{"configuration": {"x": 1}}

201 Created
{"id": "...", "type": "state", "tenant_id": "acme-corp", ...}
```

Absent header → `default` tenant (preserves v4.2 single-tenant behavior).

The cycle endpoints scope to the tenant's registry:
```
POST /cognition/run         X-Tenant-ID: acme-corp  → cycle over acme-corp's constructs
GET  /cognition/tension     X-Tenant-ID: foo-llc    → tension over foo-llc's constructs
GET  /cognition/symbol-field X-Tenant-ID: bar-inc   → bar-inc's symbol field summary
```

### `/musia/tenants/*` administrative endpoints

New router: [musia_tenants.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_tenants.py).

- `GET /musia/tenants` — list every tenant with construct count
- `GET /musia/tenants/{tenant_id}` — one tenant's summary
- `DELETE /musia/tenants/{tenant_id}` — drop a tenant's MUSIA state (other tenants unaffected)

Path namespaced under `/musia/tenants` (not `/tenants`) because the
existing platform `/tenants` router manages full tenant runtime
(budgets, quotas, isolation auditing). The MUSIA scope is narrower:
construct registry state only.

### Tenant-scoped Φ_agent filter installation

`install_phi_agent_filter()` now takes an optional `tenant_id` parameter:

```python
from mcoi_runtime.app.routers.constructs import install_phi_agent_filter
from mcoi_runtime.substrate.phi_gov import PhiAgentFilter

# Strict policy on acme-corp; default-permissive elsewhere
install_phi_agent_filter(
    PhiAgentFilter(l3=lambda d, c, a: my_strict_policy(d, c, a)),
    tenant_id="acme-corp",
)
```

A filter on tenant A does not affect writes to tenant B. Verified by
[test_multi_tenant.py::test_phi_agent_filter_isolated_per_tenant](mullu-control-plane/mcoi/tests/test_multi_tenant.py).

### Cross-tenant references rejected at the API layer

```
POST /constructs/change HTTP/1.1
X-Tenant-ID: tenant-b
{"state_before_id": "<state owned by tenant-a>"}

400 Bad Request
{"detail": "referenced state ... not in tenant tenant-b"}
```

This is structural, not policy: the registry literally cannot resolve
the reference because the construct does not exist in `tenant-b`'s
graph. There is no setting that allows cross-tenant references.

---

## Test counts

| Suite                                    | v4.2.0  | v4.3.0  |
| ---------------------------------------- | ------- | ------- |
| MCOI Python tests (existing, untouched)  | 44,500+ | 44,500+ |
| MAF Rust tests                           | 180     | 180     |
| MUSIA-specific suites                    | 350     | 365     |
| Multi-tenant isolation tests (new)       | n/a     | 15      |

Doc/code consistency check passes (94 docs scanned).

---

## Compatibility

- All v4.2.0 endpoints unchanged in URL or shape
- Absent `X-Tenant-ID` header → routed to `default` tenant; v4.2 callers see no behavior change
- `_REGISTRY` symbol still exported from `mcoi_runtime.app.routers.constructs` as a backward-compat proxy that maps to the default tenant
- `reset_registry()` now resets *all* tenants (was: the global registry)
- `install_phi_agent_filter(filter)` without `tenant_id` → installs on default tenant
- Library API (Python, no HTTP) unchanged: `STORE` is opt-in; direct `DependencyGraph` use still works

---

## What v4.3.0 still does NOT include

- **Auth-driven tenant resolution** — the header is the bearer; production needs auth middleware that derives tenant from a verified token, not a client-supplied header. v4.3.0 explicitly trusts `X-Tenant-ID`; do not deploy with public exposure.
- **Persistent tenant state** — store is in-memory; tenants are lost on process restart. Persistence integration with the existing audit log + lineage is a separate workstream.
- **Tenant onboarding/offboarding flow** — get-or-create is the only creation path. No quotas, no rate limits, no provisioning hooks.
- **Cross-tenant cascade prevention proof** — verified by tests; not yet enforced at the cascade-engine level (the engine never sees a reference outside its `DependencyGraph`, so cross-tenant cascade is structurally impossible — but a formal proof is desirable).
- **Domain adapters scoped per tenant** — the Python `run_with_ucja()` functions are tenant-naive; they operate on a fresh `SymbolField`. Wiring them to `STORE.get_or_create(tenant_id)` is straightforward but not done.

---

## Live demonstration

```python
from fastapi.testclient import TestClient
from mcoi_runtime.app.routers.constructs import router as constructs_router
from mcoi_runtime.app.routers.cognition import router as cognition_router
from fastapi import FastAPI

app = FastAPI()
app.include_router(constructs_router)
app.include_router(cognition_router)
client = TestClient(app)

# Tenant A creates 3 states
for _ in range(3):
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme-corp"},
        json={"configuration": {}},
    )

# Tenant B sees nothing
r_b = client.get("/cognition/symbol-field", headers={"X-Tenant-ID": "foo-llc"})
assert r_b.json()["size"] == 0

# Tenant A sees its own constructs
r_a = client.get("/cognition/symbol-field", headers={"X-Tenant-ID": "acme-corp"})
assert r_a.json()["size"] == 3
```

---

## Honest assessment

v4.3.0 is the structural prerequisite for any real production deployment.
The framework now isolates tenants at the registry level — the same
guarantee the existing platform's audit log and budget systems already
provide for the rest of the runtime.

What it is not, yet: production-secure. Trusting `X-Tenant-ID` from the
client is fine for development and for deployments behind a trusted
gateway, but a directly-exposed deployment would let any client
impersonate any tenant. **Auth middleware that overwrites the header
with the authenticated tenant identifier is the next required step.**

**We recommend:**
- Upgrade in place. v4.3.0 is additive; default tenant preserves v4.2 behavior.
- Wire your auth middleware to set `X-Tenant-ID` from the verified token before this header reaches the router.
- Use `install_phi_agent_filter(filter, tenant_id="...")` to apply per-tenant policy.
- Use `/musia/tenants` for observability of registry state across tenants.

---

## Contributors

Same single architect, same Mullusi project. v4.3.0 closes the
multi-tenancy gap that was the largest remaining structural prerequisite
for production use.
