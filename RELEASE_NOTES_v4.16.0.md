# Mullu Platform v4.16.0 — MUSIA Runtime (Per-Domain Chain Gating)

**Release date:** TBD
**Codename:** Domain Gate
**Migration required:** No (additive — chain stays detached by default)

---

## What this release is

Closes the v4.15.0 deferred item: chain gating now applies to
`/domains/<name>/process` runs as well as `/constructs/*` writes.

Before v4.16.0: the v4.15.0 bridge gated MUSIA *writes*, but a
deployment running a domain cycle (e.g., `POST /domains/healthcare/process`)
sidestepped the chain entirely. With v4.16.0, a single
`configure_musia_governance_chain()` call now governs both surfaces.

The v4.15.0 release notes flagged this gap explicitly under "What
v4.15.0 still does NOT include." v4.16.0 ships it.

---

## What is new in v4.16.0

### `gate_domain_run()` in the bridge

[musia_governance_bridge.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_bridge.py).

A new helper invokes the installed chain with a domain-run-shaped
`GuardContext`:

```python
from mcoi_runtime.app.routers.musia_governance_bridge import gate_domain_run

ok, reason = gate_domain_run(
    domain="healthcare",
    tenant_id="hospital-a",
    summary="prescribe rx for patient X",
    actor_identifier="dr-bob",  # optional
)
if not ok:
    # short-circuit — return blocked outcome, do not run cycle
    ...
```

Whereas `installed_validator_or_none()` adapts the chain into Φ_gov's
per-construct external_validator slot, `gate_domain_run()` invokes the
chain *directly* with a domain-action context. The shape is intentionally
distinct from the construct-write context:

| Field                 | Value                                  |
| --------------------- | -------------------------------------- |
| `operation`           | `"domain_run"` (vs. `"create"`/`"update"`) |
| `endpoint`            | `f"musia/domains/{domain}/process"`     |
| `domain`              | `"software_dev"` / `"healthcare"` / etc. |
| `tenant_id`           | resolved tenant                         |
| `summary`             | the request payload's `summary` field   |
| `authenticated_subject` | `actor_identifier` if given          |

Notably absent: `construct_type`, `construct_tier`. A domain run is not a
single-construct write — guards keying off construct fields would
mis-target a domain action, so the bridge omits them. This lets guards
write per-surface policy:

```python
def block_writes_when_pii_only_run(ctx: dict) -> GuardResult:
    if ctx.get("operation") == "domain_run" and "ssn" in ctx.get("summary", ""):
        return GuardResult(allowed=False, guard_name="pii_lockdown", ...)
    return GuardResult(allowed=True, guard_name="pii_lockdown")
```

### All six `/domains/*/process` endpoints gated

[domains.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/domains.py).

Each endpoint now runs the chain *before* the cycle. On chain rejection,
the endpoint returns 200 with a synthetic `DomainOutcome`:

```json
{
  "domain": "healthcare",
  "governance_status": "blocked: chain_rejected (blocked_by:hc_lockdown (compliance freeze))",
  "audit_trail_id": "<fresh uuid>",
  "risk_flags": ["chain_gate_rejected: blocked_by:hc_lockdown ..."],
  "plan": [],
  "metadata": {"chain_gate": "rejected", "reason": "..."},
  "tenant_id": "hospital-a",
  "run_id": null
}
```

The 200 (not 403) is intentional. `/domains/*` is a structured cycle
endpoint where every result — accepted, rejected by Φ_agent, or now
rejected by the chain — flows through the same `DomainOutcome`
envelope. Callers parse `governance_status` for the verdict; status code
remains success-of-transport. This matches v4.14.x semantics for cycle
rejections.

When the chain is detached (default) or allows the run, behavior is
unchanged from v4.15.0.

### No work happens on rejection

A blocked run:
- Skips the cycle entirely (no SCCCE, no UCJA, no construct generation)
- Skips persistence even when `?persist_run=true` is set (no `merge_run`,
  `run_id` is `null`)
- Skips construct registry mutations (verified by test:
  `test_blocked_run_does_not_persist_when_persist_run_set`)

This is the natural consequence of short-circuiting in the endpoint
handler before any cycle code runs.

### Per-endpoint coverage

All six endpoints wired with the same pattern:

```python
blocked = _gate_or_blocked_outcome(
    domain="<domain_name>", tenant_id=tenant_id, summary=payload.summary,
)
if blocked is not None:
    return blocked
```

| Endpoint                            | Domain key (in chain ctx) |
| ----------------------------------- | ------------------------- |
| POST /domains/software-dev/process  | `software_dev`            |
| POST /domains/business-process/process | `business_process`     |
| POST /domains/scientific-research/process | `scientific_research` |
| POST /domains/manufacturing/process | `manufacturing`           |
| POST /domains/healthcare/process    | `healthcare`              |
| POST /domains/education/process     | `education`               |

The domain key in the guard context is the `_` form (Python identifier
style), not the URL `-` form, so policies key off stable identifiers
unaffected by URL routing.

---

## Test counts

| Suite                                    | v4.15.0 | v4.16.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 710     | 736     |
| Domain gating tests (new)                | n/a     | 26      |

The 26 new tests cover (parametrized tests count once per parameter):

**Unit (gate_domain_run)**
- Detached chain → permissive pass
- Attached chain that allows → pass
- Attached chain that denies → blocked with guard name in reason
- `domain` key visible to guards (per-domain policy)
- `operation = "domain_run"` distinguishes from construct writes
- `endpoint` populated as `musia/domains/<x>/process`
- `construct_type` / `construct_tier` absent
- `summary` reaches guards
- `actor_identifier` when provided populates `authenticated_subject`
- No actor → no `authenticated_subject` field

**Integration (parametrized over all six endpoints)**
- Detached: each endpoint accepts a valid payload (6 tests)
- Attached + denying: each endpoint short-circuits with blocked outcome (6 tests)

**Integration (specific scenarios)**
- Chain rejection with `persist_run=true` does not leak constructs
- Per-domain policy: healthcare blocked, software-dev passes
- Summary reaches guards via end-to-end HTTP flow
- Blocked run still returns a fresh `audit_trail_id`

---

## Compatibility

- All v4.15.0 endpoints unchanged in URL or shape
- Detached chain (default) preserves v4.15.0 domain-run behavior exactly
- New `gate_domain_run()` helper is purely additive
- The blocked-outcome shape uses existing `DomainOutcome` fields — no new
  response keys, so clients with strict envelope validation continue to work
- `governance_status` adopts a new prefix (`"blocked: chain_rejected"`)
  for chain rejection, which is distinguishable from cycle-level rejection
  (`"approved"` / `"rejected: ..."`) by clients that key off the prefix

---

## Production deployment guidance

### Single chain governs both surfaces

```python
# Existing setup from v4.15.0 — unchanged
chain = build_my_governance_chain()  # rate_limit + budget + jwt + rbac
configure_musia_governance_chain(chain)

# v4.16.0: that same chain now also gates /domains/*/process runs.
# No additional configuration required.
```

### Writing per-surface policy

A guard can branch on `ctx["operation"]`:

```python
def per_surface_policy(ctx: dict) -> GuardResult:
    op = ctx.get("operation")
    if op == "domain_run":
        # domain-run-specific policy (e.g., audit trail required)
        if not ctx.get("authenticated_subject"):
            return GuardResult(allowed=False, guard_name="audit_required",
                               reason="domain runs require named actor")
    elif op in ("create", "update"):
        # write-specific policy (e.g., construct-type restrictions)
        if ctx.get("construct_type") == "boundary":
            return GuardResult(allowed=False, guard_name="boundary_lockdown",
                               reason="boundary writes restricted")
    return GuardResult(allowed=True, guard_name="per_surface_policy")
```

### Per-domain rate limits

Combined with `ctx["domain"]`, deployments can write differential rate
limits per domain — e.g., 100/min for software_dev, 10/min for
healthcare:

```python
def per_domain_rate_limit(ctx: dict) -> GuardResult:
    if ctx.get("operation") != "domain_run":
        return GuardResult(allowed=True, guard_name="per_domain_rl")
    domain = ctx.get("domain", "")
    limits = {"software_dev": 100, "healthcare": 10, "education": 50}
    threshold = limits.get(domain, 60)
    if rate_limiter.exceeded(ctx["tenant_id"], domain, threshold):
        return GuardResult(allowed=False, guard_name="per_domain_rl", ...)
    return GuardResult(allowed=True, guard_name="per_domain_rl")
```

### Audit-trail id correlation

Every blocked outcome carries a fresh `audit_trail_id`. Guards that log
their decisions should include this id so operators correlating chain
logs with HTTP responses (or with downstream alerts) have a stable handle:

```python
def auditing_guard(ctx: dict) -> GuardResult:
    decision = chain_logic(ctx)
    audit_log.write({
        "endpoint": ctx.get("endpoint"),
        "tenant": ctx.get("tenant_id"),
        "verdict": decision.allowed,
        # The handler returns a fresh audit_trail_id in the response,
        # but guards can mint or look up their own correlation id here.
    })
    return decision
```

---

## What v4.16.0 still does NOT include

- **Per-guard scope on domain runs** — like v4.15.0 writes, the chain's
  verdict is binary. A guard that wants to *modify* a domain run (e.g.,
  reduce blast_radius from "system" to "module") can't. Future work.
- **Chain context for read endpoints** — `/constructs` GET, `/domains` GET,
  `/runs` GET still bypass the chain. This is intentional; reads are
  cheaper than the chain itself, so a chain on reads would invert the
  cost model. If a deployment wants chain-gated reads (e.g., for tenant
  visibility policy), that's a separate workstream.
- **JWKS-with-RSA, distributed rate limits, multi-process backend, Rust port** — still ahead.

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
v4.14.1  import cycle fixes (patch)
v4.15.0  Φ_gov ↔ GovernanceGuardChain bridge (writes)
v4.16.0  per-domain chain gating (reads-as-cycles)
```

736 MUSIA tests; 109 docs; six domains over HTTP with full chain
governance on both write AND domain-run surfaces; multi-tenant +
multi-auth + persistent + scope-enforced + size-and-rate-bounded +
run-traceable + run-cleanable + run-exportable + paginated +
chain-gated on every governed surface.

---

## Honest assessment

v4.16.0 is small (~50 lines of bridge + ~30 of router wiring + tests),
and that smallness is the point. The v4.15.0 bridge already established
the chain↔Φ_gov contract; v4.16.0 just invokes the same chain at a
second pre-cycle gate. No new contracts, no new types, no new
configuration knobs.

The shape difference between the two surfaces (write context with
`construct_type`, domain-run context with `domain`) is the only design
decision worth flagging — we chose to keep them distinct so guards can
write surface-specific policy without needing to disambiguate
themselves. A guard that wants to apply uniformly can just ignore the
extra fields.

What it is not, yet: chain-gated reads. That would shift the cost
model — a read currently costs ~hashtable lookup; chain evaluation
might cost orders of magnitude more. We'd want a much cheaper "read
chain" path before adding that. Not v4.17.

**We recommend:**
- Upgrade in place. v4.16.0 is additive; default-detached preserves v4.15 behavior.
- If you've installed a chain via `configure_musia_governance_chain()` in v4.15, it now also gates domain runs — no additional config.
- Use `ctx["operation"]` to write per-surface policy when you need different rules for writes vs. domain runs.

---

## Contributors

Same single architect, same Mullusi project. v4.16.0 closes the
v4.15.0 "still does NOT include: per-domain governance" item one minor
release later, by reusing the bridge contract that v4.15.0 designed.
