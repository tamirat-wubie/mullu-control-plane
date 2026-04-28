# Audit F7 — Governance Package Reorganization Plan

**Status:** scoping (not yet executing)
**Audit fracture:** F7 — "governance modules scattered across `core/`, `app/`, `persistence/`, `domain_adapters/` with overlapping responsibilities"
**Author:** autopilot loop after v4.37
**Decision required:** approval of target layout + sequencing before any code moves

---

## TL;DR

The audit's framing of F7 as "scattered with overlapping responsibilities" is half right. Survey of the actual codebase shows:

- **52 governance-named files in `core/`** (out of 421 total) — yes, scattered.
- **Zero internal coupling between the canonical governance modules.** `governance_guard.py`, `audit_trail.py`, `tenant_budget.py`, `rate_limiter.py`, `jwt_auth.py`, `api_key_auth.py`, `ssrf_policy.py`, `access_runtime.py`, `tenant_gating.py`, `governance_metrics.py`, `governance_decision_log.py`, `policy_engine.py`, `content_safety.py` — all import only stdlib (and `contracts/` for `tenant_budget`'s `LLMBudget`).
- **194 caller import statements** across `mcoi/` and tests for these 15 modules. Roughly 65 in source, 130 in tests.

**Implication:** F7 is a discoverability problem, not a coupling problem. The migration is mechanical: create a `governance/` package, move files, update import paths. No design decisions about decoupling are required because the modules are *already* decoupled.

This makes F7 tractable as a 4-PR sequence rather than the "multi-week refactor" the autopilot loop's earlier read suggested.

---

## Why this matters

Operators and contributors learn the platform by reading the file tree. When 52 governance-relevant files are interleaved with 369 unrelated files in `core/`, the cost of "what's the auth surface?" is a search rather than a navigation. After v4.26–v4.37 closed every contained audit fracture, the next bottleneck on production-grade quality is **legibility** — a new operator should be able to point at one directory and say "that's the audit surface."

A reorganization also enforces a discipline that the audit Part 2 noted: when there's no obvious place for new governance code to live, contributors invent new top-level modules in `core/`. That's how 52 files happened. A `governance/` package with named sub-packages gives the next contributor a target.

---

## Survey: what's there now

### Canonical governance modules and their caller counts

| Module | Source callers | Test callers | LOC |
|---|---:|---:|---:|
| `core/governance_guard.py` | 11 | 22 | 438 |
| `core/audit_trail.py` | 8 | 20 | 619 |
| `core/tenant_budget.py` | 6 | 14 | 323 |
| `core/rate_limiter.py` | 5 | 15 | 344 |
| `core/jwt_auth.py` | 2 | 11 | 713 |
| `core/api_key_auth.py` | 2 | 11 | 312 |
| `core/access_runtime.py` | 2 | 10 | 788 |
| `core/tenant_gating.py` | 5 | 6 | 281 |
| `core/ssrf_policy.py` | 2 | 1 | 212 |
| `core/governance_decision_log.py` | — | — | 244 |
| `core/governance_metrics.py` | — | — | 205 |
| `core/policy_engine.py` | — | — | — |
| `core/content_safety.py` | — | — | — |
| **Total covered** | **45** | **110** | **~4,500** |

### Internal coupling

Importing each canonical module's source and grepping for `from mcoi_runtime.` returns:
- `governance_guard.py`: zero internal imports
- `audit_trail.py`: zero
- `tenant_budget.py`: one (`contracts.llm.LLMBudget`)
- `rate_limiter.py`: zero
- `jwt_auth.py`: zero
- `api_key_auth.py`: zero
- `ssrf_policy.py`: zero
- `access_runtime.py`: zero
- `tenant_gating.py`: zero
- `governance_metrics.py`: zero
- `governance_decision_log.py`: zero
- `policy_engine.py`: zero
- `content_safety.py`: zero
- `webhook_system.py`: one (`core.ssrf_policy.is_private_url` — added in v4.32)

**The governance surface has effectively no internal coupling.** Each module is already an independent leaf. The only cross-cuts are:
1. `webhook_system → ssrf_policy` (one edge, intentional from v4.32)
2. `audit_export → audit_trail` (within the audit family)
3. `rate_limit_quotas → rate_limiter` (within the rate-limit family)

That's it. No circular imports, no spaghetti, no dependency injection magic to untangle. The "overlapping responsibilities" the audit flagged are *naming* overlaps (`governance_guard`, `governance_metrics`, `governance_integration`, `governance_compiler`, etc.) not *behavioral* overlaps.

---

## Target layout

```
mcoi_runtime/governance/
├── __init__.py                  # re-exports the public API surface
├── auth/                        # F16, F33 (JWT hardening), F35 (env+tenant binding)
│   ├── __init__.py
│   ├── jwt.py                   # ← core/jwt_auth.py
│   ├── api_key.py               # ← core/api_key_auth.py
│   └── tenant_binding.py        # NEW — extracted from governance_guard
├── guards/                      # F2, F11, F33
│   ├── __init__.py
│   ├── chain.py                 # ← core/governance_guard.py (chain machinery)
│   ├── rate_limit.py            # ← core/rate_limiter.py
│   ├── budget.py                # ← core/tenant_budget.py
│   ├── tenant_gating.py         # ← core/tenant_gating.py
│   ├── access.py                # ← core/access_runtime.py
│   └── content_safety.py        # ← core/content_safety.py
├── audit/                       # F3, F4, F15
│   ├── __init__.py
│   ├── trail.py                 # ← core/audit_trail.py
│   ├── anchor.py                # ← core/audit_anchor.py
│   ├── export.py                # ← core/audit_export.py
│   └── decision_log.py          # ← core/governance_decision_log.py
├── network/                     # F9, F10
│   ├── __init__.py
│   ├── ssrf.py                  # ← core/ssrf_policy.py
│   └── webhook.py               # ← core/webhook_system.py
├── policy/                      # all policy_* modules
│   ├── __init__.py
│   ├── engine.py                # ← core/policy_engine.py
│   ├── enforcement.py           # ← core/policy_enforcement.py
│   ├── provider.py              # ← core/provider_policy.py
│   ├── sandbox.py               # ← core/policy_sandbox.py
│   ├── simulation.py            # ← core/policy_simulation.py
│   ├── versioning.py            # ← core/policy_versioning.py
│   └── shell.py                 # ← core/shell_policy_engine.py
└── metrics.py                   # ← core/governance_metrics.py
```

**Out of scope for this reorg** (stays in `core/`):

- Anything not directly governance: `agent_*`, `artifact_*`, `assurance_*`, `autonomous_*`, `availability_*`, etc.
- Domain-specific governance variants (`adapter_governance.py`) — these belong in their respective adapters
- `governed_session.py`, `governed_dispatcher.py`, `governed_tool_use.py`, `governed_capability_registry.py` — these orchestrate governance but aren't governance themselves; treat as `core/` consumers of the new package
- `constitutional_governance.py`, `data_governance.py`, `federated_*.py` — separate higher-order concerns; can move in a later (optional) reorg

The criterion for inclusion: **does this module enforce, audit, or carry policy?** If yes, it belongs in `governance/`. If it's an orchestrator that *uses* governance, it stays put and imports from the new package.

---

## Migration sequence (4 PRs)

### Phase 1 — Skeleton + shims (1 PR, ~150 LoC source)

**Goal:** create `governance/` package structure with each submodule re-exporting from the existing `core/` location.

```python
# mcoi/mcoi_runtime/governance/auth/jwt.py
"""Re-export shim. Real implementation lives at core/jwt_auth.py."""
from mcoi_runtime.core.jwt_auth import *  # noqa: F401, F403
from mcoi_runtime.core.jwt_auth import (  # explicit re-exports for tooling
    JWTAuthenticator,
    OIDCConfig,
    JWKSFetcher,
    JWTAuthResult,
    create_jwt_guard,
)
```

Repeat for every module in the target tree. Add tests that verify the new import paths resolve to the same objects as the old paths. **Existing callers continue to work unchanged.**

This phase is non-breaking by design. Anyone whose PR is in flight against `core/jwt_auth.py` doesn't have to rebase.

**Risk:** low. Pure additive. Worst case: revert one PR.

### Phase 2 — Migrate source callers (1 PR, ~65 import-statement edits)

**Goal:** every `mcoi/mcoi_runtime/` import of `core.{governance_guard,audit_trail,…}` switches to `governance.{guards.chain,audit.trail,…}`.

Tool: a Python script that walks `mcoi/mcoi_runtime/` and applies the rename mapping. Verify with `python -m pytest mcoi/tests/ -q` after.

The shim layer from Phase 1 means **rollback is just a revert** — no semantic change, only path change.

**Risk:** low-medium. Mechanical. Tests catch any miss.

### Phase 3 — Migrate test imports (1 PR, ~130 import-statement edits)

**Goal:** every test file follows the new import path.

Same script as Phase 2, applied to `mcoi/tests/` and `tests/`.

**Risk:** low. Tests pass or fail loudly.

### Phase 4 — Remove shims + delete old `core/` files (1 PR)

**Goal:** the old `core/governance_guard.py` etc. files are deleted; `governance/` modules contain the real implementation; the shim re-exports are removed.

Mechanically: move the file content from `core/X.py` to `governance/Y/X.py`, delete the shim, update the file's docstring/governance-scope header.

**Risk:** the highest of the four phases (file moves are real diffs), but **gates pass before merging**: full mcoi suite + reflective contract guard + receipt coverage invariant. Any caller that wasn't migrated in Phase 2/3 fails loudly.

---

## Why this is a 4-PR sequence and not one big-bang PR

**Each phase is independently revertable.** If Phase 4 surfaces a CI failure that wasn't caught earlier, reverting it leaves `governance/` shims still working — production isn't affected.

**Each phase is reviewable.** The largest PR (Phase 3 — test migrations) is mechanical noise; reviewers can spot-check rather than line-by-line read 130 changes.

**Each phase preserves bisectability.** If a regression appears 2 weeks after the reorg, `git bisect` can identify which phase introduced it and revert just that phase.

A single 4,500-LoC big-bang PR fails all three of those properties. The 4-PR sequence costs one extra week of calendar time to merge, but bounds the risk per merge to one revertable scope.

---

## What stays unchanged

- **No public API breakage.** Every symbol importable from `core/X.py` before the reorg is importable from `governance/Y/X.py` after. The shim phase guarantees this.
- **No test rewrites.** Tests update import paths; their assertions stay the same.
- **No reflective-contract changes.** The contracts pin invariants of behavior, not file paths.
- **No release notes.** The v-tag this lands under is incidental — F7 closure is the changelog entry, not a feature.

---

## Estimated cost

| Phase | LoC touched | Reviewer time | CI time |
|---|---:|---:|---:|
| 1. Skeleton + shims | ~150 (new) | 30 min | 10 min |
| 2. Source migration | ~65 (edits) | 45 min | 10 min |
| 3. Test migration | ~130 (edits) | 30 min | 10 min |
| 4. Shim removal + file moves | ~4,500 (moves, no semantic delta) | 1 hour | 10 min |
| **Total** | **~4,800** | **~3 hours** | **40 min** |

Calendar time: 1 week if one phase ships per business day, plus a bake period after Phase 1 to catch concurrent PRs.

---

## What this plan does NOT solve

The audit's F7 framing also implied a deeper reshape — collapsing `governed_*` orchestrators (`governed_session`, `governed_dispatcher`, `governed_tool_use`, `governed_capability_registry`) into the new package. The plan above explicitly leaves them in `core/` because:

1. They orchestrate governance; they aren't governance.
2. Moving them creates real coupling questions (a session imports auth, audit, budget, rate-limit — does the orchestrator belong inside or outside the package it consumes?).
3. The audit's primary concern was **legibility of the audit surface**, which the 15-module migration addresses.

If after Phase 4 the audit team thinks the orchestrators should also move, that's a separate design discussion — and a separate plan doc.

---

## Decision points for review

Before executing this plan, the project lead should confirm:

1. **Target layout.** Does the proposed `governance/{auth, guards, audit, network, policy}` taxonomy match the team's mental model? (If not, reshape now — re-renaming after Phase 4 doubles the work.)
2. **Inclusion criteria.** Should `governed_session.py` and friends move now, or stay in `core/`? (The plan currently says stay.)
3. **Phasing pace.** One phase per business day, or spread over a longer bake period?
4. **Concurrent-PR policy.** During Phase 2/3 (the migration weeks), do we freeze new PRs that touch the affected paths, or accept some rebase cost?

Once those four questions have answers, this plan is executable.

---

## Honest assessment

The autopilot loop's earlier read of F7 as "multi-week architectural work" was based on the surface-level scattering. The actual structure of the code makes F7 the cheapest of the remaining audit fractures to close — once you accept that the work is "rename and re-import" rather than "decompose and decouple."

The reason it was deferred: closing it requires touching 200+ files in a coordinated way, which is uncomfortable to do during a contained-fracture sprint. With the audit fractures done and the deployment doc shipped, the next contributor has the calendar room to execute this without it cutting into other commitments.

**Recommendation:** approve this plan, schedule Phase 1 for the next business day, and commit to a 4-business-day execution window. The total source code delta is mostly file moves; the value is operator-facing legibility of the audit surface.
