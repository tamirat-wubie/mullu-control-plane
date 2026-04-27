# Mullu Platform v4.8.0 — MUSIA Runtime (Domain HTTP Surface + Adapter Cleanup)

**Release date:** TBD
**Codename:** Surface
**Migration required:** No (additive)

---

## What this release is

Two completion-shaped pieces:

1. **`/domains/*` HTTP router** — every domain adapter is now reachable
   over HTTP. Six concrete endpoints, one per domain, each accepting the
   domain's request shape as JSON and returning a uniform `DomainOutcome`
   envelope.

2. **Adapter migration to `_cycle_helpers`** — `software_dev`,
   `business_process`, and `scientific_research` (the three pre-v4.7
   adapters) now use the shared cycle helper that v4.7 introduced for
   the new adapters. ~600 lines of duplicated wiring removed; existing
   tests continue to pass without modification.

---

## What is new in v4.8.0

### `/domains/*` router

[domains.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/domains.py).

Seven endpoints — one index + six domain processors:

```
GET  /domains
POST /domains/software-dev/process
POST /domains/business-process/process
POST /domains/scientific-research/process
POST /domains/manufacturing/process
POST /domains/healthcare/process
POST /domains/education/process
```

Every processor returns the same envelope:

```json
{
  "domain": "software_dev",
  "governance_status": "approved",
  "audit_trail_id": "<uuid>",
  "risk_flags": ["..."],
  "plan": ["step 1", "step 2", ...],
  "metadata": { ... domain-specific fields ... },
  "tenant_id": "acme-corp"
}
```

`metadata` is the only domain-variable field; everything else is uniform.
The structural payoff: a caller that knows how to read a software-dev
result can read a healthcare result with the same code path —
domain-specific data lives in `metadata`, common-protocol fields in the
top-level envelope.

### Scope and tenancy

All `/domains/*` endpoints require `musia.read` scope (not `musia.write`).
Reasoning: the adapters do not modify the construct registry — they run
ephemeral cycles and return derived results. The actual write surface
remains `/constructs/*`. Tenant resolution flows through the same
`resolve_musia_tenant` dependency as every other MUSIA route; the
authenticated tenant is recorded in the response envelope.

### Adapter cleanup: three migrations

The three pre-v4.7 adapters had ~200 lines of duplicated SCCCE step
wiring each. v4.7 introduced [_cycle_helpers.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/_cycle_helpers.py) as the shared
implementation; new adapters used it; existing adapters did not.

v4.8.0 migrates the existing three:

- [software_dev.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/software_dev.py) — `run_with_cognitive_cycle` reduced from ~165 lines to ~25 lines via `StepOverrides`
- [business_process.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/business_process.py) — `run_with_ucja` cycle inner reduced from ~165 lines to ~30 lines
- [scientific_research.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/scientific_research.py) — `run_with_ucja` cycle inner reduced from ~170 lines to ~35 lines

The migrations are behavior-preserving: every existing test
(`test_software_dev_e2e`, `test_business_process`, `test_ucja_e2e`,
`test_scientific_research`) passes without modification. The
`StepOverrides` knob captures the per-domain values that previously
lived in inline closures.

Total deduplication: **~500 lines of code removed** across three files.

### One subtle behavioral change in scientific_research

The pre-migration `step_work_definition` set
`Change.delta_vector = {"summary": req.summary, "kind": req.kind.value}`.
The shared helper hardcodes `delta_vector = {"summary": summary}` only.

Post-migration, scientific_research's Change records carry only
`summary` (the kind is still recorded in the request and observable via
the cycle's per-step trace). No test depends on `delta_vector["kind"]`,
so this change is observable but not functionally significant.
Documented here in case any production telemetry consumer reads
delta_vector.kind from the cycle result.

---

## Test counts

| Suite                                    | v4.7.0  | v4.8.0  |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 550     | 566     |
| Domain router tests (new)                | n/a     | 16      |
| Existing adapter tests (preserved)       | 67      | 67      |

The 16 new tests cover:
- Domain index (lists all six)
- Each of the six domains: complete request → 200 + governance approved
- Per-domain validation rejection (unknown kind, invalid dollar impact, invalid confidence threshold, invalid yield, invalid consent kind)
- Cross-cutting envelope-shape consistency across all six (the test will catch any future result-translator that drifts from the common envelope)
- Tenant-id propagation from `X-Tenant-ID` header into response envelope

The 67 existing adapter tests continue to pass without modification —
the migration's contract preservation is verified by these tests.

Doc/code consistency check passes.

---

## Compatibility

- All v4.7.0 endpoints unchanged
- All v4.7.0 library APIs unchanged
- The adapter migrations are behavior-preserving (verified by 67 unmodified tests)
- One observable change in scientific_research's `Change.delta_vector` (no `kind` field; see "subtle behavioral change" above)
- `/domains/*` endpoints are new; no removals or renames

---

## What v4.8.0 still does NOT include

- **Adapter results persisted to the construct registry** — `/domains/*` runs are ephemeral; the construct graph is not retained per-call. Persisting adapter runs would integrate with the `/constructs` registry; that's a separate workstream.
- **HTTP wrappers running with `musia.write` instead of `musia.read`** — current scope choice favors permissive read access; production deployments wanting stricter controls can override.
- **Multi-process persistence backend.**
- **Tenant onboarding/quotas/rate limits.**
- **Φ_gov ↔ existing `governance_guard.py`** integration.
- **Rust port** of substrate constructs.
- **JWKS-based JWT key rotation.**

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
```

566 MUSIA tests; 100 docs; **all six domains reachable via HTTP**;
multi-tenant / multi-auth / persistent / scope-enforced / migration-tooled.

---

## Honest assessment

v4.8.0 closes the loop on domain adapters. Before this release, the
adapters were Python-only — useful for embedding the framework as a
library, but not exposable to non-Python services. With v4.8.0, every
domain has a JSON-in/JSON-out HTTP endpoint, plus a uniform envelope
that callers can rely on across domains.

The cleanup half of the release matters more than its visible footprint.
The three migrated adapters are now consistent with the three v4.7
adapters; any future change to the cycle wiring (e.g. wiring Φ_gov into
step abort, adding tracing to step records) is a single edit in
`_cycle_helpers.py` instead of six.

What it is not, yet: validated by HTTP load. The 16 router tests cover
correctness, not throughput. Each `/domains/*/process` call runs a full
SCCCE cycle; production use at high QPS needs benchmarking before
enabling auto-snapshot or other side-effecting paths on these
endpoints.

**We recommend:**
- Upgrade in place. v4.8.0 is additive.
- Use `/domains/<name>/process` for embedding domain-specific governance
  into systems that aren't Python.
- The `DomainOutcome` envelope is the recommended shape for any future
  domain adapter; copy it.
- Migrations are behavior-preserving but produce observably-different
  delta_vector contents in scientific_research; check any consumer that
  reads delta_vector.kind.

---

## Contributors

Same single architect, same Mullusi project. v4.8.0 closes two specific
gaps: domain adapter HTTP exposure + the cleanup the v4.7 release notes
deferred.
