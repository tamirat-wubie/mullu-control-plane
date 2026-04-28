# Mullu Platform v4.41.0 — Test-side Import Migration (Audit F7 Phase 3)

**Release date:** TBD
**Codename:** Cascade
**Migration required:** No

---

## What this release is

Phase 3 of the audit-F7 reorganization. v4.38 created the `mcoi_runtime.governance` package with shim re-exports; v4.39 migrated source-side caller imports to the new paths; v4.41 finishes the same migration on the test side.

**68 test files updated. 108 module-imports rewritten.** No behavior changes.

After this PR, every import across `mcoi/mcoi_runtime/` and `mcoi/tests/` references the new `governance.*` paths (with three exceptions noted below). Phase 4 (file moves + shim removal) is now unblocked.

---

## What is new in v4.41.0

### 68 test files migrated

The mechanical rewrite from `mcoi_runtime.core.X` → `mcoi_runtime.governance.Y.X` for every governance-relevant import. The mapping is the same as v4.39:

| Old path | New path |
|---|---|
| `core.jwt_auth` | `governance.auth.jwt` |
| `core.api_key_auth` | `governance.auth.api_key` |
| `core.governance_guard` | `governance.guards.chain` |
| `core.rate_limiter` | `governance.guards.rate_limit` |
| `core.tenant_budget` | `governance.guards.budget` |
| `core.tenant_gating` | `governance.guards.tenant_gating` |
| `core.access_runtime` | `governance.guards.access` |
| `core.content_safety` | `governance.guards.content_safety` |
| `core.audit_trail` | `governance.audit.trail` |
| `core.audit_anchor` | `governance.audit.anchor` |
| `core.audit_export` | `governance.audit.export` |
| `core.governance_decision_log` | `governance.audit.decision_log` |
| `core.ssrf_policy` | `governance.network.ssrf` |
| `core.webhook_system` | `governance.network.webhook` |
| `core.policy_engine` | `governance.policy.engine` |
| `core.policy_enforcement` | `governance.policy.enforcement` |
| `core.provider_policy` | `governance.policy.provider` |
| `core.policy_sandbox` | `governance.policy.sandbox` |
| `core.policy_simulation` | `governance.policy.simulation` |
| `core.policy_versioning` | `governance.policy.versioning` |
| `core.shell_policy_engine` | `governance.policy.shell` |
| `core.governance_metrics` | `governance.metrics` |

### Files NOT migrated (intentional)

Three exceptions where the new path doesn't carry what the test needs. The new shim only re-exports the **public API**; tests reaching into private internals or third-party module references must talk to the canonical `core/` module.

1. **`test_v4_38_governance_package_shims.py`** — explicitly imports from BOTH old and new paths to verify the shim contract. Skipped entirely by the migration script.
2. **Private-symbol imports** in 4 test files — split into two import lines (public from new path, private from `core/`):
   - `test_audit_trail.py` — `_recompute_entry_hash`, `_canonical_hash_v1`, `_canonical_content_v1` from `core.audit_trail`
   - `test_jwt_auth.py` — `_b64url_decode`, `_b64url_encode` from `core.jwt_auth`
   - `test_v4_31_atomic_audit_append.py` — `_canonical_hash_v1` from `core.audit_trail`
   - `test_v4_33_jwt_hardening.py` — `_default_jwks_fetcher` from `core.jwt_auth`
3. **`test_content_safety.py::test_normalize_content_preserves_ethiopic_runs`** — patches `content_safety.unicodedata.normalize`. The shim doesn't re-export the third-party `unicodedata` module, so the test reverts that one import to `core.content_safety`.

Each exception is a one-liner that says "this stays on `core/` until Phase 4 moves the implementation." All four are documented inline.

### Test fixture fix from Phase 2 preserved

`test_governed_session.py::test_from_env_records_optional_bootstrap_failures` was already fixed in Phase 2 to patch both the source module and the shim namespace. The migration script avoided breaking that fix; the helper line that imports `from mcoi_runtime.core import governance_decision_log` (used by `monkeypatch.setattr`) remains pointed at `core/`.

---

## Compatibility

- **Zero breaking changes for callers.** The shim layer guarantees identity preservation; tests run identically.
- **No semantic changes.** Same objects, same behavior, different import paths.
- **All existing tests pass.** Including the v4.38 shim verification, the v4.39 source-migration verification, and the v4.40 hash-chain regression tests.

---

## Test counts

**Full mcoi suite: 48,788 passed, 26 skipped, 0 failures.**

That's +37 from the v4.40 baseline (48,751) — accounting for parallel-track work that landed on main while this PR was in flight, not v4.41-specific test additions. v4.41 itself adds zero new tests; it's purely a path migration.

---

## Production deployment guidance

Nothing to do. This release is purely test-side restructuring. Production code paths are unchanged from v4.40.

---

## What's left in the F7 sequence

**Phase 4** is the only remaining phase: physically move the 21 implementation files from `core/` into their `governance/` locations and delete the shim re-exports. Mechanically:

```
mcoi_runtime/core/jwt_auth.py        →  mcoi_runtime/governance/auth/jwt.py
mcoi_runtime/core/api_key_auth.py    →  mcoi_runtime/governance/auth/api_key.py
mcoi_runtime/core/governance_guard.py →  mcoi_runtime/governance/guards/chain.py
... (and 18 more)
```

Plus removing the 22 shim files (which are now redundant).

Risk: medium. By the time Phase 4 lands, every caller is already on the new path (verified by Phases 2 + 3). The actual move is invisible to runtime behavior. The risk is the 4 private-symbol imports — those must update from `core.X` to `governance.Y.X` as part of the move (since the implementation file IS at the new location after Phase 4).

Calendar: ~30 minutes of script time + suite verification + PR review.

---

## Audit roadmap status

```
✅ F2/F3/F4/F5/F6/F9/F10/F11(t+i)/F12/F15/F16 + JWT hardening
✅ F15 follow-up — empty-file race (v4.40)
✅ F7 Phase 1 — skeleton + shims (v4.38)
✅ F7 Phase 2 — source-side imports (v4.39)
✅ F7 Phase 3 — test-side imports (v4.41)  ← this PR
⏳ F7 Phase 4 — file moves + shim removal
⏳ F8 — MAF substrate disconnect (PyO3, multi-week)
```

After Phase 4, F7 closes entirely. Remaining audit work: F8 (MAF substrate, multi-week PyO3 effort).

---

## Honest assessment

v4.41 is mechanical: 108 import-statement rewrites across 68 files plus 5 small fixups for tests that reach into private API or third-party module references. The `from mcoi_runtime.core import X` pattern needed special handling (one regex to peel governance modules out of multi-name import lists; one manual fix where the rewrite produced the wrong shape).

The interesting bits:

- **The 4 private-symbol imports are all in audit/JWT tests.** That's because audit and JWT have the most internal structure (canonical-hash helpers, base64url encoders, default JWKS fetcher). After Phase 4 these collapse to one import each.
- **The `unicodedata` patch in `test_content_safety` was the only test that reached into a third-party module reference.** That's a test-design smell — testing implementation by patching a transitive dependency is fragile. But fixing the test pattern is out of scope; for now it just stays pointed at `core/`.

Phase 4 is now mechanically straightforward. Every caller knows the new path. The only thing left is moving the bytes.

**We recommend:**
- Land v4.41 and bake one business day before Phase 4.
- Phase 4 closes F7 entirely and removes ~660 LoC of shim boilerplate (since the targets are gone).
- After Phase 4, the audit-grade contained-fracture loop is genuinely finished.
