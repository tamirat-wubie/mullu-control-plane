# Mullu Platform v4.42.0 — Governance Package Implementation Move (Audit F7 Phase 4)

**Release date:** TBD
**Codename:** Anchor
**Migration required:** No — every caller is already on the new path after Phases 2 + 3

---

## What this release is

**Phase 4 of the audit-F7 reorganization. Closes F7 entirely.**

v4.38 created the `mcoi_runtime.governance` shim package. v4.39 + v4.41 migrated every caller to the new paths. v4.42 physically moves the 21 implementation files out of `core/` into `governance/`, deletes the shim re-exports, and updates 5 private-symbol imports + a few stragglers.

After v4.42:
- `mcoi_runtime/governance/` contains the 21 governance modules, each at its canonical post-reorg location.
- `mcoi_runtime/core/jwt_auth.py` and the 20 other governance files are **gone** from `core/`.
- The 22 v4.38 shim files are **gone** from `governance/` (replaced by their implementation targets).
- The audit surface lives in one discoverable directory.

---

## What is new in v4.42.0

### 21 files moved

Each `core/<module>.py` was copied into its target `governance/<subpkg>/<name>.py` location, overwriting the shim re-export, and the original `core/` file was deleted:

```
core/jwt_auth.py                 → governance/auth/jwt.py
core/api_key_auth.py             → governance/auth/api_key.py
core/governance_guard.py         → governance/guards/chain.py
core/rate_limiter.py             → governance/guards/rate_limit.py
core/tenant_budget.py            → governance/guards/budget.py
core/tenant_gating.py            → governance/guards/tenant_gating.py
core/access_runtime.py           → governance/guards/access.py
core/content_safety.py           → governance/guards/content_safety.py
core/audit_trail.py              → governance/audit/trail.py
core/audit_anchor.py             → governance/audit/anchor.py
core/audit_export.py             → governance/audit/export.py
core/governance_decision_log.py  → governance/audit/decision_log.py
core/ssrf_policy.py              → governance/network/ssrf.py
core/webhook_system.py           → governance/network/webhook.py
core/policy_engine.py            → governance/policy/engine.py
core/policy_enforcement.py       → governance/policy/enforcement.py
core/provider_policy.py          → governance/policy/provider.py
core/policy_sandbox.py           → governance/policy/sandbox.py
core/policy_simulation.py        → governance/policy/simulation.py
core/policy_versioning.py        → governance/policy/versioning.py
core/shell_policy_engine.py      → governance/policy/shell.py
core/governance_metrics.py       → governance/metrics.py
```

22 v4.38 shim files removed, 21 implementation files relocated. Net: -1 file (the new top-level `governance/__init__.py` and 5 sub-package `__init__.py` files stay).

### Import-graph cleanup

Several import-graph adjustments were needed:

1. **Internal cross-references inside the moving files.** 4 files (`tenant_gating`, `content_safety`, `audit_export`, `webhook_system`) imported other moving modules via `from mcoi_runtime.core.X import` — rewritten to the new `governance.Y.X` paths before the move.

2. **Relative imports (`from ..contracts.X` / `from .Y`).** 6 moved files used relative imports that referenced `..contracts/`, `..persistence/`, `..adapters/`, or non-moving `core/` siblings. All converted to absolute `mcoi_runtime.X` paths.

3. **Sibling-renamed reference.** `governance/policy/versioning.py` had `from .policy_engine import ...` referring to its sibling — but that sibling was renamed to `engine.py` during the move. Updated to `from .engine import`.

4. **5 callers of `core/`-relative private symbols** in non-moving files (`core/access_runtime_integration.py`, `core/change_assurance.py`, `core/policy_enforcement_integration.py`, `core/policy_simulation_integration.py`, `core/runtime_kernel.py`). Each had `from .X import Y` where X moved out of core/; rewritten to absolute new paths.

5. **5 private-symbol caller imports + 1 unicodedata patch path** updated to the new `governance.Y.X` location (since the implementation now lives there, not at `core/`):
   - `postgres_governance_stores.py`: `_canonical_hash_v1` → `governance.audit.trail`
   - `test_audit_trail.py`: `_recompute_entry_hash`, `_canonical_hash_v1`, `_canonical_content_v1` → `governance.audit.trail`
   - `test_jwt_auth.py`: `_b64url_decode`, `_b64url_encode` → `governance.auth.jwt`
   - `test_v4_31_atomic_audit_append.py`: `_canonical_hash_v1` → `governance.audit.trail`
   - `test_v4_33_jwt_hardening.py`: `_default_jwks_fetcher` → `governance.auth.jwt`
   - `test_content_safety.py`: `unicodedata.normalize` patch path → `governance.guards.content_safety`

6. **String-literal references** in `monkeypatch.setattr` calls (e.g. `"mcoi_runtime.core.ssrf_policy.socket.getaddrinfo"`) updated to the new module paths via batch replacement.

### v4.38 shim verification test rewritten

The v4.38 shim verification test pinned the contract that `governance.X` re-exported from `core.X`. After Phase 4 the contract is different: `governance.X` is the implementation; the `core.X` paths no longer exist.

The rewritten test pins the post-Phase-4 invariant:

- `TestPackageStructure` — every governance subpackage imports
- `TestNewPathsResolve` — every governance module's expected public symbols resolve
- `TestOldPathsAreGone` — **the 22 retired `core.X` paths must all raise `ModuleNotFoundError`** (catches any future PR that tries to resurrect a stale path)

The `RETIRED_CORE_PATHS` literal is constructed from a tuple of suffixes joined to `"mcoi_runtime.core."` — the literal is split across lines to make it batch-rename-resistant. Future migration scripts won't accidentally rewrite the retired-path list.

---

## Compatibility

- **Every caller of `mcoi_runtime.governance.*`** continues to work — Phases 2 + 3 already moved them.
- **Direct `mcoi_runtime.core.<governance_module>` imports** raise `ModuleNotFoundError`. If your code still has any (audit your private forks), update to `mcoi_runtime.governance.Y.X`.
- **Behavior is byte-identical.** No public API changed; only file locations.
- **Logger names** in 22 modules changed from `mcoi_runtime.core.X` to `mcoi_runtime.governance.Y.X` (Python's logger name follows the module name automatically). If you have monitoring keyed on the old logger names, update your log queries.

---

## Test counts

**Full mcoi suite: 48,807 passed, 26 skipped, 2 failures (both pre-existing on `origin/main` — `scripts/` path issue, not v4.42).**

Tests counted:
- **TestOldPathsAreGone** — 1 new test confirms all 22 retired `core.X` paths are gone
- **TestNewPathsResolve** — 2 tests verify every governance module imports + symbols resolve
- The 9 v4.38 shim-identity tests **deleted** (their contract no longer applies)

Net: 48,807 vs 48,788 baseline = **+19 net tests** from parallel-track work that landed during the F7 phases, minus the 9 removed shim tests, plus the 3 new Phase 4 verification tests.

---

## What this release is NOT

- **It does not rename anything.** The new locations were chosen by the v4.38 plan; v4.42 just relocates files into them.
- **It does not change behavior.** The implementation files moved bytes-for-bytes (modulo the 4 internal-import rewrites in those files).
- **It does not touch `core/` orchestrators.** `governed_session.py`, `governed_dispatcher.py`, `governed_tool_use.py`, etc. remain in `core/`. Per the F7 plan, those are *consumers* of governance, not governance themselves.

---

## Audit roadmap status

```
✅ F2/F3/F4/F5/F6/F9/F10/F11(t+i)/F12/F15/F16 + JWT hardening
✅ F15 follow-up — empty-file race (v4.40)
✅ F7 — governance package reorganization (v4.38 → v4.39 → v4.41 → v4.42)  ← FULLY CLOSED
⏳ F8 — MAF substrate disconnect (PyO3, multi-week)
```

**16 of 17 audit fractures fully closed in code.** Only F8 (PyO3 Rust↔Python substrate) remains, and that's multi-week infra work outside the contained-fracture loop.

---

## Honest assessment

v4.42 is a moderate diff (~5,000 LoC of file content moved, ~30 import-statement edits across the source tree, ~5 caller-side fixups for private symbols and string-literal references) but the *behavioral* delta is zero. Every line of moved code does the same thing it did before; only the location changed.

The interesting moments during execution:
- **Relative imports broke first.** Files using `from ..contracts.X` resolved relative to their NEW location after the move, which doesn't have a `contracts/` sibling. Each one converted to an absolute path.
- **One sibling rename.** `policy_versioning.py` had `from .policy_engine import` — its sibling was renamed to `engine.py` during the move. The same module was now reachable as `.engine` instead of `.policy_engine`. One-line fix.
- **String-literal paths in `monkeypatch.setattr`.** Tests using `"mcoi_runtime.core.ssrf_policy.socket.getaddrinfo"` to inject DNS failures needed string-literal updates. Regex didn't catch these — they were inside string quotes, not Python import statements.
- **Greedy substring match.** `mcoi_runtime.core.policy_simulation` is a prefix of `mcoi_runtime.core.policy_simulation_integration`. The first rewrite was too aggressive; reverted manually for the 3 affected `*_integration` test files.

The lesson: **batch-renaming string literals is more dangerous than batch-renaming imports.** Imports follow a strict syntactic shape; literals can be anywhere. For Phase 4 the blast radius was small (3 files needed reversal), but a future migration touching a more popular path would benefit from a parser-aware tool rather than `str.replace`.

After this release, **F7 is closed**. The audit-grade contained-fracture loop has no further mechanical work. The remaining open items are F8 (PyO3 substrate, multi-week) and operational hardening (stress test under realistic load, security review pass, observability dashboards) — all out of scope for the autopilot loop's "one PR, one fracture" shape.

**We recommend:**
- Land v4.42 and verify no production deployment has a private fork that imports `mcoi_runtime.core.<governance_module>`.
- After bake, plan F8 as a multi-week effort with explicit human direction (build tooling decisions, FFI ABI, etc.) — not autopilot territory.
- Treat the audit-fracture series as feature-complete for v4.x.
