# Mullu Platform v4.38.0 — Governance Package Skeleton (Audit F7 Phase 1)

**Release date:** TBD
**Codename:** Skeleton
**Migration required:** No (additive — every existing import path keeps working)

---

## What this release is

Phase 1 of the audit-F7 reorganization. Introduces a new `mcoi_runtime.governance` package whose submodules re-export the canonical governance API from the existing `mcoi_runtime.core.*` modules.

Phase 1 is **non-breaking by design**: every caller continues to work via the old `mcoi_runtime.core.X` paths; the new `mcoi_runtime.governance.Y.X` paths are additive aliases. Phase 4 of the F7 sequence (still ahead) will move the implementation files into the new package and remove the shims.

The full reorg plan (4 PRs) lives in [`docs/GOVERNANCE_PACKAGE_REORG_PLAN.md`](docs/GOVERNANCE_PACKAGE_REORG_PLAN.md). This release executes Phase 1 only.

---

## Why this matters

Before v4.38, the `mcoi_runtime.core/` directory held 421 Python files, of which 52 are governance-related. A new operator or contributor asking "what's the audit surface?" had to grep — there was no directory to point at. v4.38 creates that directory.

The audit's F7 framing was "scattered with overlapping responsibilities." Survey of the actual codebase showed:
- Yes, scattered (52 files in `core/`)
- **Zero internal coupling** between the canonical governance modules — they all import only stdlib
- 194 caller import statements across mcoi/ and tests for the top 15 governance modules

So F7 is a discoverability problem, not a coupling problem. The migration is mechanical: package skeleton → migrate source imports → migrate test imports → move files. v4.38 is the first of these four phases.

---

## What is new in v4.38.0

### `mcoi_runtime/governance/` package

```
mcoi_runtime/governance/
├── __init__.py
├── auth/
│   ├── jwt.py              ← re-exports core/jwt_auth
│   └── api_key.py          ← re-exports core/api_key_auth
├── guards/
│   ├── chain.py            ← re-exports core/governance_guard
│   ├── rate_limit.py       ← re-exports core/rate_limiter
│   ├── budget.py           ← re-exports core/tenant_budget
│   ├── tenant_gating.py    ← re-exports core/tenant_gating
│   ├── access.py           ← re-exports core/access_runtime
│   └── content_safety.py   ← re-exports core/content_safety
├── audit/
│   ├── trail.py            ← re-exports core/audit_trail
│   ├── anchor.py           ← re-exports core/audit_anchor
│   ├── export.py           ← re-exports core/audit_export
│   └── decision_log.py     ← re-exports core/governance_decision_log
├── network/
│   ├── ssrf.py             ← re-exports core/ssrf_policy
│   └── webhook.py          ← re-exports core/webhook_system
├── policy/
│   ├── engine.py           ← re-exports core/policy_engine
│   ├── enforcement.py      ← re-exports core/policy_enforcement
│   ├── provider.py         ← re-exports core/provider_policy
│   ├── sandbox.py          ← re-exports core/policy_sandbox
│   ├── simulation.py       ← re-exports core/policy_simulation
│   ├── versioning.py       ← re-exports core/policy_versioning
│   └── shell.py            ← re-exports core/shell_policy_engine
└── metrics.py              ← re-exports core/governance_metrics
```

22 shim modules + 6 `__init__.py` files = 28 files total.

Each shim follows the same pattern:

```python
"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at mcoi_runtime.core.jwt_auth. This module
provides the canonical post-reorg import path; callers may use either
the old core.jwt_auth path or the new governance.auth.jwt path. The
shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove
the shim.
"""
from mcoi_runtime.core.jwt_auth import (  # noqa: F401
    JWKSFetcher,
    JWTAlgorithm,
    JWTAuthResult,
    JWTAuthenticator,
    OIDCConfig,
)

__all__ = (
    "JWKSFetcher",
    "JWTAlgorithm",
    "JWTAuthResult",
    "JWTAuthenticator",
    "OIDCConfig",
)
```

### Identity preservation

The shim re-exports the **same object** as the original `core/` module — not a copy, not a subclass. Importing `JWTAuthenticator` from either path yields the identical class object:

```python
import mcoi_runtime.core.jwt_auth as old
import mcoi_runtime.governance.auth.jwt as new
assert old.JWTAuthenticator is new.JWTAuthenticator  # True
```

This is what makes Phase 1 truly non-breaking: `isinstance` checks, identity comparisons, and frame-based introspection all keep working across the import boundary.

### Verification tests

`mcoi/tests/test_v4_38_governance_package_shims.py` covers:

- `TestPackageStructure` — top-level package + 5 sub-packages all import
- `TestShimsImportCleanly` — every advertised shim path resolves
- `TestIdentityPreservation` — every re-exported symbol is the *same object* as the canonical core/ location
- `TestExplicitDunderAll` — each shim's `__all__` matches its expected export set
- `TestNoBackwardBreakage` — the original `core/` paths still work

---

## Compatibility

- **Zero breaking changes.** Every existing `from mcoi_runtime.core.X import Y` continues to work unchanged.
- **No semantic differences.** The shims re-export the original objects; behavior is byte-identical.
- **No new dependencies.** Stdlib only.
- **No reflective-contract changes.** Contracts pin behavior, not file paths.

The only observable difference: `import mcoi_runtime.governance` is now possible.

---

## What is NOT in this release

This is Phase 1 of 4. Out of scope here:

- **Source-code import migrations** (Phase 2). The ~65 internal imports from `core/X` to `governance.Y.X` happen in a separate PR.
- **Test import migrations** (Phase 3). The ~130 test imports.
- **File moves + shim removal** (Phase 4). The actual relocation.
- **`tenant_binding.py` extraction.** The reorg plan calls for a new module extracted from `governance_guard.py`'s tenant logic; that's a content change, not a re-export, so it lives in a later phase.
- **`governed_*` orchestrators.** `governed_session.py`, `governed_dispatcher.py`, etc. stay in `core/` per the plan's scoping decision (they orchestrate governance, but aren't governance themselves).

---

## Test counts

9 new tests in [`test_v4_38_governance_package_shims.py`](mullu-control-plane/mcoi/tests/test_v4_38_governance_package_shims.py).

Full mcoi suite: **48,746 passed, 26 skipped, 0 failures** (+9 over v4.37 baseline).

No existing tests modified. No source code modified.

---

## Production deployment guidance

Nothing to do. This release is pure-additive scaffolding. Existing deployments don't need any config change.

If you're a contributor or operator browsing the codebase, you can now look in `mcoi/mcoi_runtime/governance/` to find the audit surface in one place.

---

## Audit roadmap status

```
✅ F2/F3/F4/F5/F6/F9/F10/F11(t+i)/F12/F15/F16 + JWT hardening
🔄 F7 — Phase 1 of 4 shipped (skeleton + shims)  ← this PR
⏳ F7 Phase 2 — migrate source imports
⏳ F7 Phase 3 — migrate test imports
⏳ F7 Phase 4 — move files + remove shims
⏳ F8 — MAF substrate disconnect (PyO3, multi-week)
```

---

## Honest assessment

v4.38 is small (~30 LoC in each shim × 22 shims = ~660 LoC of mostly-mechanical re-export boilerplate, plus 250 LoC of verification tests). The interesting design decisions were already made in the reorg plan ([`docs/GOVERNANCE_PACKAGE_REORG_PLAN.md`](docs/GOVERNANCE_PACKAGE_REORG_PLAN.md)). This PR just executes Phase 1 of that plan.

The value isn't in the code; it's in the **enforcement of a discoverable layout**. Once the package exists, the next contributor who needs to add a governance module has an obvious target. They don't have to invent a new top-level `core/governance_*.py` file. That's how 52 governance-named files happened in `core/`; the new layout makes it harder to repeat.

The risk is also small. The shim layer is provably equivalent to the original (identity check passes for every symbol). Phase 2 onward will edit caller imports — those are mechanical and gate-checked. Phase 4 moves files — but by then every caller is already on the new path, so the move is an internal rename.

**We recommend:**
- Land Phase 1 (this PR) and bake for at least one business day.
- Schedule Phase 2 (source-import migration) once the team has confirmed no concurrent PR is mid-review against any of the 21 governance-touching `core/` files.
- Phases 3 and 4 follow the same cadence.
