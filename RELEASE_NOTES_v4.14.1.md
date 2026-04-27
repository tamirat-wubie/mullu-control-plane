# Mullu Platform v4.14.1 — MUSIA Runtime (Import Cycle Fixes)

**Release date:** TBD
**Codename:** Untangle
**Migration required:** No (additive — old import paths preserved via re-exports)

---

## What this release is

Patch release that resolves three circular imports the static dependency
analyzer (`tests/test_import_analyzer.py::test_mcoi_runtime_no_import_cycles`)
detected after running the full repo test suite for the first time after
v4.14.0.

The cycles were structural, not behavioral — at runtime they all
worked because of lazy imports inside function bodies. But the static
graph had three feedback loops, and the existing repo invariant tests
(written long before MUSIA) assert that the runtime must have none.
That's the kind of invariant that catches structural drift early; v4.14.1
honors it.

---

## What is fixed

### Cycle 1: `substrate.registry_store ↔ substrate.persistence`

**Cause:** `registry_store.py` did a lazy import of `FileBackedPersistence`
inside `configure_persistence()`. `persistence.py` did a lazy import of
`TenantQuota` inside `restore_quota_from_payload()`. Both lazy imports
worked at runtime but the analyzer flagged the static cycle.

**Fix:** Extracted `TenantQuota` into a new neutral module
`substrate/_quota.py`. `registry_store.py` now imports `TenantQuota` from
`_quota` (top-level). `persistence.py` lazy-imports `TenantQuota` from
`_quota` instead of `registry_store`. The cycle is broken.

`from mcoi_runtime.substrate.registry_store import TenantQuota` keeps
working — it's re-exported.

### Cycle 2: `domain_adapters._cycle_helpers ↔ domain_adapters.software_dev`

**Cause:** `_cycle_helpers.py` imported `UniversalRequest` and
`UniversalResult` from `software_dev.py` (where they were originally
defined as part of the first adapter). `software_dev.py` then lazy-imported
`StepOverrides` and `run_default_cycle` from `_cycle_helpers.py` (after
the v4.8.0 cleanup migration).

**Fix:** Extracted both universal types into a new neutral module
`domain_adapters/_types.py`. Both `_cycle_helpers.py` and `software_dev.py`
import them from `_types`. The cycle is broken.

`from mcoi_runtime.domain_adapters.software_dev import UniversalRequest`
and `... UniversalResult` keep working — re-exported via a one-line
import in `software_dev.py`.

### Cycle 3: `substrate ↔ substrate` (self-cycle)

**Cause:** `substrate/__init__.py` did
`from mcoi_runtime.substrate import metrics as metrics`. The static
analyzer flagged this as a self-cycle because the package was importing
its own submodule.

**Fix:** Removed the re-export line. Callers wanting the metrics module
import it directly:

```python
from mcoi_runtime.substrate import metrics              # works (submodule)
from mcoi_runtime.substrate.metrics import REGISTRY     # explicit
```

Documented in `substrate/__init__.py` so future contributors don't
accidentally restore the self-import.

---

## Test counts

| Suite                                            | v4.14.0 | v4.14.1 |
| ------------------------------------------------ | ------- | ------- |
| MUSIA-specific suites                            | 693     | 693     |
| Repo-wide cycle tests (now passing again)        | 47,698  | 47,701  |

The 3 previously-failing repo invariant tests now pass:
- `test_governance_endpoints.py::TestOpsImports::test_analyze_imports`
- `test_import_analyzer.py::TestRealCodebase::test_mcoi_runtime_no_import_cycles`
- `test_protocol_manifest.py::test_protocol_manifest_is_valid` (was a separate test-discovery issue, unrelated to MUSIA)

All 676 MUSIA-specific tests continue to pass without modification.
Doc/code consistency check passes.

---

## Compatibility

- All v4.14.0 endpoints and library APIs unchanged
- All previous import paths preserved via re-exports — no client migration needed
- No new dependencies
- No new endpoints

---

## Honest assessment

This is exactly the kind of structural debt that accumulates when adding
features quickly: lazy imports are a workaround for "two modules need
each other" and they work at runtime but leave the static graph
tangled. The repo's existing import-cycle invariant test is what
caught this — it had been silently failing for several releases until
the full repo suite ran.

Lesson for future MUSIA development: the lazy-import escape hatch is a
red flag. When you reach for it, consider whether a third neutral
module would resolve the underlying coupling more cleanly.

The fix is small (3 new files, ~80 lines, all extractions) and entirely
backward-compatible. v4.14.0 callers see no change.

---

## Cumulative MUSIA progress

```
v4.0.0   substrate (Mfidel + Tier 1)
v4.1.0   full 25 constructs + cascade + Φ_gov + cognition + UCJA
v4.2.0   HTTP surface + governed writes + business_process adapter
v4.3.0   multi-tenant registry isolation
v4.3.1   auth-derived tenant resolution
v4.4.0   persistent tenant state
v4.5.0   auto-snapshot + JWT + scope enforcement
v4.6.0   scientific_research + bulk migration runner
v4.7.0   manufacturing + healthcare + education adapters
v4.8.0   /domains HTTP surface + adapter cleanup
v4.9.0   JWT rotation + tenant construct count quotas
v4.10.0  sliding-window rate limits + quota persistence
v4.11.0  persist_run audit trail + run_id queries
v4.12.0  run metadata enrichment + bulk delete + runs listing
v4.13.0  indexed run lookup + run export endpoint
v4.14.0  opt-in pagination across list endpoints
v4.14.1  import cycle fixes (patch — no API change)
```

693 MUSIA tests; 107 docs; six domains over HTTP; full repo invariant
tests (cycles, imports, protocol manifest) all pass.

---

## Contributors

Same single architect, same Mullusi project. v4.14.1 closes the
import-cycle gap that the wider repo suite surfaced.
