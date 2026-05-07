# Mullu Platform v4.2.0 — MUSIA Runtime (HTTP Surface + Governed Writes)

**Release date:** TBD
**Codename:** Surface
**Migration required:** No (additive)

---

## What this release is

v4.1.0 shipped the full MUSIA framework as a Python library. v4.2.0 makes
it reachable over HTTP with governed writes, and ships a second domain
adapter to demonstrate the framework is not single-domain.

The framework now has:
- A library API (since v4.0.0) — `from mcoi_runtime.substrate.constructs import State`
- A function-level cycle runner (since v4.1.0) — `SCCCECycle().run(field)`
- A UCJA pipeline gate (since v4.1.0) — `UCJAPipeline().run(payload)`
- An HTTP surface (this release) — `POST /constructs/state`, `POST /ucja/define-job`
- Governed writes (this release) — every `/constructs/*` POST routes through Φ_gov
- A second concrete domain (this release) — `business_process` joins `software_dev`

---

## What is new in v4.2.0

### HTTP routers — the API surface

Four new routers, registered into the existing FastAPI server at
`mcoi_runtime/app/server_http.py`:

#### `/mfidel/*` — substrate atom access (stateless)
- `GET /mfidel/grid` — grid summary, including the three known-empty positions
- `GET /mfidel/atom/{row}/{col}` — atomic fidel lookup (`is_empty=true` for unfilled slots)
- `GET /mfidel/overlay/{row}/{col}` — vowel overlay resolution

#### `/constructs/*` — construct CRUD with Φ_gov-gated writes
- `GET /constructs?tier=N&type_filter=X` — list with tier/type filters
- `GET /constructs/{id}` — read one
- `GET /constructs/{id}/dependents` — list constructs that reference this one
- `POST /constructs/state | change | causation | constraint | boundary` — Tier 1 writes
- `DELETE /constructs/{id}` — refuses to orphan dependents (HTTP 409)

Every write is governed: a `ProposedDelta` is built, Φ_agent's 6-level
filter runs, then `Φ_gov.evaluate()` decides. On rejection, the response
is HTTP 403 with structured detail (proof state, blocking filter level,
rejected delta) — never a silent rejection.

#### `/cognition/*` — SCCCE cycle interface
- `POST /cognition/run` — runs the cycle over the current registry snapshot, returns convergence reason + ProofState + 15-step trace
- `GET /cognition/tension` — tension calculation without running a cycle (configurable per-tier weights via query params)
- `GET /cognition/symbol-field` — registry summary (size, tier breakdown, type breakdown)

#### `/ucja/*` — pipeline gate
- `POST /ucja/qualify` — runs L0 only; cheap pre-filter
- `POST /ucja/define-job` — runs L0–L9; halts on first non-PASS layer; full draft + per-layer trace returned

### Governed writes — Φ_gov on the API write path

Previous releases let any well-formed write into the registry. v4.2.0
routes every `POST /constructs/*` through Φ_gov:

```
POST /constructs/state {…}
  → Construct.__post_init__ (structural validation)
  → ProposedDelta(create, …)
  → Φ_agent 6-level filter
  → Φ_gov cascade analysis
  → either register OR HTTP 403 with judgment record
```

Test/runtime hook `install_phi_agent_filter()` lets a deployment install
a custom filter stack; default permissive lets the pipeline exercise its
control flow without blocking.

### Second domain adapter — `business_process`

Demonstrates the framework is not software-specific. Translates business
workflows (approvals, escalations, SLA tasks, procurement, on/offboarding,
policy changes) into the universal causal framework.

Mapping highlights:
- **Approval chain** → `authority_required` (each approver becomes a separate authority entry)
- **SLA deadline** → constraint with `violation_response: escalate` (distinct from `block`)
- **Dollar impact ≥ $100k** → risk flag suggesting dual approval
- **Enterprise blast radius** → broadcast change announcement requirement
- **Tight SLA (< 4h)** → escalation path must be pre-armed

Same `run_with_ucja()` pattern as `software_dev`. End-to-end UCJA → SCCCE
flow verified by 17 tests.

---

## Test counts

| Suite                                    | v4.1.0  | v4.2.0  |
| ---------------------------------------- | ------- | ------- |
| MCOI Python tests (existing, untouched)  | 44,500+ | 44,500+ |
| MAF Rust tests                           | 180     | 180     |
| MUSIA-specific suites                    | 285     | 313+17 = 330 |
| HTTP router tests (new)                  | n/a     | 31      |
| Governance-on-write tests (new)          | n/a     | 3       |
| Business process adapter tests (new)     | n/a     | 17      |

Doc/code consistency check passes (92 docs scanned).

---

## What v4.2.0 still does NOT include

Honest deferral list:

- **Per-tenant construct registry** — current `_REGISTRY` is process-global; multi-tenancy is Phase 4 work
- **Persistence beyond process lifetime** — registry is in-memory; integration with audit log + lineage is a separate workstream
- **Φ_gov → existing `core/governance_guard.py` chain wiring** — the Φ_gov contract has the slot (`external_validators=...`); the actual chain integration is a separate task because guard chain has its own auth + error model
- **Domain adapters beyond `software_dev` and `business_process`** — `scientific_research`, `manufacturing`, `healthcare`, `education` arrive in v4.3+
- **Rust port** of substrate constructs — Python-only
- **Bulk proof migration tool binary** (`mcoi migrate-proofs`) — mapping table + spec exist; runner does not
- **HTTP exposure of cycle step callbacks** — by design; step callbacks are Python functions, exposing them over HTTP would be code-execution-as-a-service

---

## Compatibility

- All v4.1.0 endpoints unchanged
- All v4.1.0 library APIs unchanged
- The new construct write path through Φ_gov is **default-permissive**: existing test code that builds constructs directly (not through the router) is unaffected
- `install_phi_agent_filter()` is opt-in; default is the permissive `PhiAgentFilter()`
- v1 proof reads/writes still supported (dual-write lands in v4.3.0)

---

## Live demonstration

A `software_dev` request gets the same end-to-end flow as before, plus a
new `business_process` parallel:

```python
from mcoi_runtime.domain_adapters import (
    BusinessActionKind, BusinessRequest, business_run_with_ucja,
)

result = business_run_with_ucja(BusinessRequest(
    kind=BusinessActionKind.APPROVAL,
    summary="approve marketing budget Q3",
    process_id="proc-001",
    initiator="alice",
    approval_chain=("manager-bob", "director-carol"),
    sla_deadline_hours=24.0,
    affected_systems=("erp", "finance_db"),
    acceptance_criteria=("budget_within_cap", "policy_compliance"),
    dollar_impact=50_000.0,
    blast_radius="department",
))
# result.governance_status == "approved"
# result.workflow_steps includes "Route to approver: manager-bob",
#                                 "Route to approver: director-carol"
# result.risk_flags == () for $50k; flags dual-approval if ≥ $100k
```

And via HTTP:

```
POST /ucja/define-job HTTP/1.1
Content-Type: application/json
{ "purpose_statement": "...", "boundary_specification": {...}, ... }

200 OK
{ "accepted": true, "draft": { "is_complete": true, ... },
  "layer_results": [ {"layer": "L0_qualification", "verdict": "pass"}, ... ] }
```

---

## Honest assessment

v4.2.0 closes the loop from "library that runs" to "service that serves."
A non-Python caller can now hit the framework over HTTP, get governed
writes, qualify requests, run the UCJA pipeline, and read back full
audit-grade traces. The shape of v4.2.0 matches what the platform was
always supposed to be — an external interface to the cognitive runtime,
not just a Python embedding.

What it is not, yet: a multi-tenant production system. The registry is
in-process and unscoped; persistence happens only via the existing audit
log; Φ_gov plugs in but is default-permissive. Production deployments
need to wire the registry per-tenant and install non-trivial Φ_agent
filters before this is ready for live workloads.

**We recommend:**
- Upgrade in place. v4.2.0 is additive.
- Begin building applications against the HTTP surface — it's the
  intended integration boundary, not the Python library.
- Wire `install_phi_agent_filter()` with your policy before going live;
  default-permissive is for development, not production.
- Build the next domain adapter using `business_process.py` as the
  reference; it's deliberately compact (~400 lines) so the pattern is
  easy to copy.

---

## Contributors

Same single architect, same Mullusi project. v4.2.0 is the first release
where the framework has both a working runtime (since v4.1.0) and an
external surface (this release) — the two halves of "control plane" are
both present.
