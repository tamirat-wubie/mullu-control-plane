# Mullu Platform v4.43.0 — Governance Architecture Documentation

**Release date:** TBD
**Codename:** Atlas
**Migration required:** No (docs only)

---

## What this release is

Documentation and docstring updates for the post-F7 governance package. After v4.42.0 closed F7 by physically moving 21 implementation files into `mcoi_runtime/governance/`, the layout is stable and discoverable. v4.43 makes that layout *navigable* — an operator or contributor can now read one document and understand:

- What lives in `governance/` and what doesn't
- The five architectural invariants every governance module must preserve
- How to add a new governance module without breaking the audit-grade properties

---

## What is new

### `docs/GOVERNANCE_ARCHITECTURE.md`

New top-level reference, ~7,000 words, sections:

1. **Package at a glance** — full directory listing with one-line per module
2. **What lives outside `governance/`** — orchestrators, domain-specific variants, and the inclusion criterion
3. **Five architectural invariants** — atomic SQL doctrine, identity preservation, fail-closed defaults, bounded error messages, connection-pool-safe storage
4. **Adding a new governance module** — sub-package picker, import-graph minimality, public API discipline, test-naming convention
5. **How to find what enforces what** — the search-by-string workflow that works because of bounded error strings
6. **What `governance/` does NOT do** — explicit non-goals
7. **Stability commitments** — what we promise to keep stable vs what may change in minor releases
8. **Audit roadmap status** — final state with all 16 closed fractures + the one remaining (F8)

### `mcoi_runtime/governance/__init__.py` rewrite

Replaces the v4.38 "Phase 1 reorg" docstring with the post-F7 architectural reference. Lists the package layout and the five invariants as the contract.

### Sub-package docstrings rewritten

All 5 sub-packages (`auth/`, `guards/`, `audit/`, `network/`, `policy/`) had their `__init__.py` docstrings rewritten from "Phase 1 - re-export shim" to actual module-list summaries with audit-fracture references.

`metrics.py` is the one top-level module; its docstring is the implementation file's content (no `__init__.py` doc to update).

---

## Compatibility

Pure documentation. Zero behavior change.

---

## Test counts

Full mcoi suite: **48,807 passed, 26 skipped, 0 failures** (same as v4.42 baseline).

---

## Audit roadmap status

```
✅ F2/F3/F4/F5/F6/F7/F9/F10/F11/F12/F15/F16 + JWT hardening + F15 follow-up
⏳ F8 — MAF substrate disconnect (PyO3, multi-week)
```

16 of 17 audit fractures closed in code. `docs/GOVERNANCE_ARCHITECTURE.md` is the canonical reference for what was built; `docs/PRODUCTION_DEPLOYMENT.md` is the canonical reference for how to operate it.

---

## Honest assessment

v4.43 is small (~750 lines of documentation) but it's the missing keystone. The v4.26–v4.42 series shipped the audit-fracture closures; this release lands the *contract* that future contributors operate against. Without this doc, the next person adding a governance module would have to reverse-engineer the invariants from the existing code; with it, they have a written specification.

The five architectural invariants are not aspirational — every one is implemented and tested. They're listed here so they survive personnel changes.

**We recommend:**
- Read `GOVERNANCE_ARCHITECTURE.md` if you're contributing to `governance/`
- Read `PRODUCTION_DEPLOYMENT.md` if you're operating Mullu
- Read `MAF_RECEIPT_COVERAGE.md` if you're working on the receipt-coverage ratchet
- The three together cover the audit surface end-to-end
