# Mullu Platform v4.39.0 — Source-side Import Migration (Audit F7 Phase 2)

**Release date:** TBD
**Codename:** Reroute
**Migration required:** No (callers within `mcoi/` automatically use new paths; old `core.X` paths still work via shims)

---

## What this release is

Phase 2 of the audit-F7 reorganization (see [`docs/GOVERNANCE_PACKAGE_REORG_PLAN.md`](docs/GOVERNANCE_PACKAGE_REORG_PLAN.md), Phase 1 shipped as v4.38.0 / [PR #409](https://github.com/tamirat-wubie/tamirat-wubie/mullu-control-plane/pull/409)).

v4.38 created the `mcoi_runtime.governance` package with shim re-exports. v4.39 migrates source-side caller imports to use the new paths.

**28 source files updated. 59 module-imports rewritten.** No semantic changes — same objects, different import paths.

---

## What is new in v4.39.0

### Migrated callers

Every source file under `mcoi/mcoi_runtime/` that imported one of the 21 governance modules from `core/` now imports from the corresponding `governance.*` shim path:

| Old | New |
|---|---|
| `mcoi_runtime.core.jwt_auth` | `mcoi_runtime.governance.auth.jwt` |
| `mcoi_runtime.core.api_key_auth` | `mcoi_runtime.governance.auth.api_key` |
| `mcoi_runtime.core.governance_guard` | `mcoi_runtime.governance.guards.chain` |
| `mcoi_runtime.core.rate_limiter` | `mcoi_runtime.governance.guards.rate_limit` |
| `mcoi_runtime.core.tenant_budget` | `mcoi_runtime.governance.guards.budget` |
| `mcoi_runtime.core.tenant_gating` | `mcoi_runtime.governance.guards.tenant_gating` |
| `mcoi_runtime.core.access_runtime` | `mcoi_runtime.governance.guards.access` |
| `mcoi_runtime.core.content_safety` | `mcoi_runtime.governance.guards.content_safety` |
| `mcoi_runtime.core.audit_trail` | `mcoi_runtime.governance.audit.trail` |
| `mcoi_runtime.core.audit_anchor` | `mcoi_runtime.governance.audit.anchor` |
| `mcoi_runtime.core.audit_export` | `mcoi_runtime.governance.audit.export` |
| `mcoi_runtime.core.governance_decision_log` | `mcoi_runtime.governance.audit.decision_log` |
| `mcoi_runtime.core.ssrf_policy` | `mcoi_runtime.governance.network.ssrf` |
| `mcoi_runtime.core.webhook_system` | `mcoi_runtime.governance.network.webhook` |
| `mcoi_runtime.core.policy_engine` | `mcoi_runtime.governance.policy.engine` |
| `mcoi_runtime.core.policy_enforcement` | `mcoi_runtime.governance.policy.enforcement` |
| `mcoi_runtime.core.provider_policy` | `mcoi_runtime.governance.policy.provider` |
| `mcoi_runtime.core.policy_sandbox` | `mcoi_runtime.governance.policy.sandbox` |
| `mcoi_runtime.core.policy_simulation` | `mcoi_runtime.governance.policy.simulation` |
| `mcoi_runtime.core.policy_versioning` | `mcoi_runtime.governance.policy.versioning` |
| `mcoi_runtime.core.shell_policy_engine` | `mcoi_runtime.governance.policy.shell` |
| `mcoi_runtime.core.governance_metrics` | `mcoi_runtime.governance.metrics` |

### What was NOT migrated

- **Shim files in `mcoi_runtime/governance/*`** — they re-export from `core/`, so they keep importing from `core/` (otherwise circular).
- **Implementation files in `mcoi_runtime/core/<module>.py`** — these *are* the real modules; reorging their own imports waits for Phase 4 (file moves).
- **One private-symbol import** — `postgres_governance_stores.py` imports `_canonical_hash_v1` (an underscore-prefixed private helper) from `audit_trail`. Private symbols stay on the canonical `core.audit_trail` path; the public shim only re-exports public API.

### Test fixture updates for shim transparency

Two test fixtures in `test_governed_session.py` use `monkeypatch.setattr` / `monkeypatch.setitem(sys.modules, ...)` to inject failures into the bootstrap path. Pre-Phase-2 these patched the source modules directly; post-Phase-2 the bootstrap goes through the shim, which caches re-exported symbols at import time.

The fix: **also rebind the symbol on the shim**. Each affected test now patches both:

```python
# Pre-existing: patch source module
monkeypatch.setattr(governance_decision_log, "GovernanceDecisionLog", _raise_optional)
# Added: also patch shim namespace
from mcoi_runtime.governance.audit import decision_log as _shim
monkeypatch.setattr(_shim, "GovernanceDecisionLog", _raise_optional)
```

This is the only test-side change in this PR. The full test migration (~130 imports) lands in Phase 3.

---

## Compatibility

- **Zero breaking changes for external callers.** The `core/X` paths still work via the v4.38 shim layer.
- **Within `mcoi_runtime/`, callers now use `governance.Y.X` paths.** Anyone reading the source code will see the new layout.
- **Identity preserved.** `JWTAuthenticator` imported from either path is the *same class object*.
- **No new dependencies.**

---

## Test counts

Full mcoi suite: **48,746 passed, 26 skipped, 0 failures** (no net change from v4.38; all new test work was fixture updates, not new tests).

The 9 v4.38 shim-verification tests still pass — identity and `__all__` invariants hold across the migration.

---

## Production deployment guidance

Nothing to do. This release is purely internal restructuring:

- Same code paths, same behavior.
- Same env vars, same error codes.
- Same Prometheus metrics.

If you have monitoring keyed on import-time stack traces, the module names in those traces will now read `mcoi_runtime.governance.auth.jwt.OIDCConfig.__post_init__` instead of `mcoi_runtime.core.jwt_auth.OIDCConfig.__post_init__`. Function names and behavior are unchanged.

---

## Audit roadmap status

```
✅ F2/F3/F4/F5/F6/F9/F10/F11(t+i)/F12/F15/F16 + JWT hardening
✅ F7 Phase 1 — skeleton + shims (v4.38.0)
✅ F7 Phase 2 — source-side import migration (v4.39.0)  ← this PR
⏳ F7 Phase 3 — test-side import migration (~130 imports)
⏳ F7 Phase 4 — file moves + shim removal
⏳ F8 — MAF substrate disconnect (PyO3 work)
```

---

## Honest assessment

v4.39 is mechanical: ~60 import statements rewritten across 28 files, plus two test-fixture updates to handle the shim's import-time symbol caching. The actual diff is mostly noise — 4-character renames in import paths.

The instructive bit was the test fixture issue. `monkeypatch.setattr(module, "Name", ...)` only affects callers that look up `Name` on `module`. Once the shim does `from core.X import Name`, the shim has its own `Name` reference; patching `core.X.Name` doesn't propagate.

The robust fix would be to make every shim use PEP 562's lazy `__getattr__` so symbol lookup is always live. That's overkill for two test cases — the pragmatic fix is to also patch the shim namespace, which is what we did.

If a future test pattern shows up that needs the same fix in many places, we can revisit and make the shims lazy. For now, two `monkeypatch.setattr` lines in two tests is the smallest correct change.

**We recommend:**
- Land Phase 2 (this PR) and bake at least one business day before Phase 3.
- Phase 3 will be larger (~130 test-import edits) but mechanically identical to Phase 2.
- Phase 4 (file moves + shim removal) can land any time after Phase 3 is stable.
