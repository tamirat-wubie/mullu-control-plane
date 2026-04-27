# Mullu Platform v4.4.0 — MUSIA Runtime (Persistent Tenant State)

**Release date:** TBD
**Codename:** Anchor
**Migration required:** No (additive — persistence is opt-in)

---

## What this release is

v4.3.x put multi-tenant isolation and auth-derived tenant resolution in
place but kept the registry in memory only. Process restart wiped every
tenant's constructs.

v4.4.0 makes that registry survive restart. Each tenant's full graph
(constructs + dependent edges) serializes to a single JSON file via an
opt-in persistence backend. Snapshots are atomic; loads restore exact
construct identity (UUIDs, timestamps, tier, type, all field values).

The framework can now run as a long-lived service.

---

## What is new in v4.4.0

### `mcoi_runtime.substrate.persistence`

New module: [persistence.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/persistence.py).

- **`construct_to_dict(c)`** / **`dict_to_construct(d)`** — round-trip every Tier 1–5 construct. UUID references, datetimes, enums, MfidelSignature, tuples, sets all preserved.
- **`snapshot_graph(tenant_id, graph)`** / **`restore_graph(payload)`** — full DependencyGraph round-trip including dependent edges.
- **`FileBackedPersistence(directory)`** — atomic writes (`os.replace` after temp file), `save/load/list_tenants/delete` API.
- **`SCHEMA_VERSION = "1"`** — recorded in every snapshot; future migrations have an explicit anchor.

### Type registry completeness check

Persistence module load asserts that every `ConstructType` enum value
has a class binding. Adding a new tier without updating the persistence
registry fails at import time, not at first save.

```python
def _verify_type_registry_complete() -> None:
    missing = set(ConstructType) - set(_TYPE_TO_CLASS.keys())
    if missing:
        raise RuntimeError(
            f"persistence type registry is incomplete: missing {sorted(...)}"
        )
```

### Store integration

`TenantedRegistryStore` gained four methods (all no-op without an
attached backend):

- `attach_persistence(backend)` / `detach_persistence()`
- `snapshot_tenant(tenant_id)` / `snapshot_all()`
- `load_tenant(tenant_id)` / `load_all()`

Convenience: `configure_persistence(directory)` attaches a default
`FileBackedPersistence`.

```python
from mcoi_runtime.substrate.registry_store import (
    STORE,
    configure_persistence,
)

# At startup
configure_persistence("/var/lib/mullu/musia")
loaded = STORE.load_all()  # restore every persisted tenant
print(f"loaded {len(loaded)} tenants")
```

### HTTP endpoints

Three new endpoints on the existing `/musia/tenants/{id}` path:

- `POST /musia/tenants/{tenant_id}/snapshot` — write current graph to disk
- `POST /musia/tenants/{tenant_id}/load` — restore from disk
- `DELETE /musia/tenants/{tenant_id}/snapshot` — remove the persisted file

All return HTTP 409 when persistence is not configured (so misconfigured
deployments fail cleanly rather than silently dropping snapshots).

---

## What is NOT persisted

Honest list:

- **Φ_agent filters** — they are Python callables, not data. After load, the tenant's filter is the default permissive one. Production deployments re-install custom filters at startup via `install_phi_agent_filter(filter, tenant_id="...")`.
- **The tension calculator's per-tenant weights** — also code; reset on load. Most deployments use the same weights everywhere; if not, the cycle config is per-request anyway.
- **The substrate path metrics** (the v3.13.1 soak counters) — these are observational, not state.
- **Auth state** (`APIKeyManager`) — separate concern, has its own persistence patterns elsewhere in the platform.

---

## Test counts

| Suite                                    | v4.3.1  | v4.4.0  |
| ---------------------------------------- | ------- | ------- |
| MCOI Python tests (existing, untouched)  | 44,500+ | 44,500+ |
| MUSIA-specific suites                    | 378     | 416     |
| Persistence tests (new)                  | n/a     | 38      |

The 38 new tests cover:
- Round-trip for every concrete construct type (parametrized over 11 representative types; full registry coverage verified by load-time check)
- Round-trip for constructs with UUID-typed scalar fields
- Round-trip for constructs with UUID-typed tuple fields (Pattern.instance_state_ids etc.)
- Round-trip for constructs with string-typed tuple fields
- MfidelSignature preservation
- DependencyGraph dependent-edge preservation
- Schema version mismatch rejection
- File backend atomic write, list, delete, missing-file behavior
- Empty-tenant-id rejection
- Store-level snapshot-then-load cycle (including dropping in-memory state then reloading)
- `load_all()` mass restore
- HTTP endpoint behavior including 409 when persistence unconfigured

Doc/code consistency check passes.

---

## Compatibility

- All v4.3.1 endpoints unchanged in URL or shape
- Persistence is **opt-in** — without `configure_persistence()`, the runtime is identical to v4.3.1
- Schema version `"1"` covers all 25 construct types
- The store is single-process; multi-process deployments need a shared backend (S3, postgres) — `FileBackedPersistence` is the reference implementation, not the only one

---

## Production deployment guidance

```python
# Startup
from mcoi_runtime.substrate.registry_store import (
    STORE,
    configure_persistence,
)
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.constructs import install_phi_agent_filter

# 1. Wire auth (v4.3.1)
configure_musia_auth(api_key_manager)

# 2. Wire persistence (v4.4.0)
configure_persistence("/var/lib/mullu/musia")
loaded_tenants = STORE.load_all()

# 3. Re-install per-tenant Φ_agent filters (not persisted)
for tid, filter_obj in your_filter_config.items():
    install_phi_agent_filter(filter_obj, tenant_id=tid)
```

Snapshots are not auto-written. For a save-on-write pattern, call
`STORE.snapshot_tenant(tenant_id)` from your write path after a
successful Φ_gov approval. For a periodic flush pattern, schedule
`STORE.snapshot_all()` on a timer.

---

## What v4.4.0 still does NOT include

- **Auto-snapshot-on-write** — explicit save calls only
- **Multi-process backends** — file-based; single-process only. S3/postgres would slot into the same `FileBackedPersistence` interface.
- **Compaction / pruning** — every snapshot is a full graph; old snapshots aren't kept (they're overwritten in place). For point-in-time recovery, integrate with the existing audit log + lineage subsystem.
- **JWT auth integration** — still API-key only
- **Per-route scope enforcement** — auth is binary
- **Tenant onboarding/quotas/rate limits**
- **More domain adapters** (`scientific_research`, `manufacturing`, `healthcare`, `education`)
- **Rust port**
- **Bulk proof migration tool binary**

---

## Honest assessment

v4.4.0 is the structural prerequisite for v4.x to be more than a demo.
A long-lived service that loses every tenant on restart is a toy. With
this release, the runtime can crash, get redeployed, get migrated to
new hardware, and come back with the same construct graph it left
with — provided someone called `snapshot_*` before the restart.

What it is not, yet: durable in the face of partial writes that span
multiple tenants. Each tenant's snapshot is atomic individually; a
crash mid-batch leaves some tenants on the new graph and some on the
old. For the v4.4.0 use case (single-process service), this is fine
because tenants are independent. For multi-process or transactional
deployments, the next release should add a journal + replay pattern
similar to the existing audit log.

**We recommend:**
- Upgrade in place. v4.4.0 is additive.
- For dev/single-process: call `configure_persistence("./snapshots")` and call `STORE.snapshot_all()` periodically. That's enough.
- For production: wire `STORE.snapshot_tenant(tenant_id)` into your write path and `STORE.load_all()` into your startup.
- For multi-process: hold off until the journal+replay landing in a future release.

---

## Contributors

Same single architect, same Mullusi project. v4.4.0 is the "boring but
necessary" release — no new conceptual ground, but the framework
crosses from prototype to deployable here.
