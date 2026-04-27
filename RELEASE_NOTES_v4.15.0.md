# Mullu Platform v4.15.0 — MUSIA Runtime (Φ_gov ↔ GovernanceGuardChain Bridge)

**Release date:** TBD
**Codename:** Bridge
**Migration required:** No (additive — chain is detached by default)

---

## What this release is

Closes the longest-deferred integration gap in MUSIA: the existing
platform's `GovernanceGuardChain` (rate limits, budgets, tenant guards,
JWT, RBAC, content safety — `core/governance_guard.py`) now plugs into
MUSIA's Φ_gov via the `external_validators` slot.

Before v4.15.0: MUSIA writes ran through MUSIA's own Φ_agent filter but
NOT through the existing chain. Two parallel governance paths, neither
aware of the other. v4.15.0 makes them one.

This was on the deferred list since v4.1.0 — "wraps the existing guard
chain in Φ_gov signature" was promised then but never wired. v4.15.0
ships it.

---

## What is new in v4.15.0

### `mcoi_runtime.app.routers.musia_governance_bridge`

New module: [musia_governance_bridge.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_governance_bridge.py).

```python
from mcoi_runtime.app.routers.musia_governance_bridge import (
    configure_musia_governance_chain,
)
from mcoi_runtime.core.governance_guard import (
    GovernanceGuardChain,
    create_rate_limit_guard,
    create_budget_guard,
)

chain = GovernanceGuardChain()
chain.add(create_rate_limit_guard(rate_limiter))
chain.add(create_budget_guard(budget_mgr))

configure_musia_governance_chain(chain)
# Now every POST /constructs/* runs the chain alongside Φ_agent.
```

The bridge translates between the two contracts:
- `GovernanceGuardChain.evaluate(dict) → GuardChainResult` (existing platform)
- `(ProposedDelta, GovernanceContext, Authority) → (bool, str)` (MUSIA Φ_gov)

The chain's verdict joins Φ_agent's: BOTH must approve. Either's denial
yields HTTP 403 with the rejection reason.

### Specific rejection reasons in `Judgment.reason`

[phi_gov.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/phi_gov.py).

Before v4.15.0, when an external validator rejected a delta, the
specific reason was discarded. The Judgment said only "all 1 deltas
rejected" — useful for counts but not for attribution.

Now the first specific rejection reason surfaces in `Judgment.reason`:

```
"blocked_by:rate_limit (rate limited)"          # chain rejection
"phi_agent_blocked_at:L3_NORMATIVE"              # filter rejection
"cascade_rejected:depth_or_dependency_violation" # cascade rejection
"policy_violation"                               # arbitrary external
```

This makes 403 responses self-attributing — clients can see which guard
denied without reading the rejected_deltas array. Existing test that
asserted on the generic "rejected" text was updated; the new contract is
strictly more informative.

### Chain context bridging

The bridge populates the chain's `GuardContext` from MUSIA's request
state so guards that key off familiar fields work without modification:

| Guard expects        | Bridge populates from           |
| -------------------- | ------------------------------- |
| `tenant_id`          | `GovernanceContext.tenant_id`   |
| `endpoint`           | `f"musia/constructs/{operation}"` |
| `method`             | `"POST"` or `"DELETE"` derived from operation |
| `authenticated_subject` | `Authority.identifier`        |
| `authenticated_tenant_id` | `GovernanceContext.tenant_id` |
| `construct_type`     | `delta.payload["type"]`         |
| `construct_tier`     | `delta.payload["tier"]`         |
| `operation`          | `delta.operation`               |

Existing rate-limit and RBAC guards work unchanged. Custom guards can
inspect `construct_type` / `construct_tier` / `operation` for
MUSIA-specific policy ("no Boundary creates from non-admin"...).

### Defensive: chain exception → denial, not propagation

If a guard raises an unexpected exception, the bridge logs it at WARNING
and returns `(False, "chain_exception:<ExceptionType>")`. This matches
the existing `GovernanceGuard.check()`'s defensive behavior — a buggy
guard fails closed, not open.

### Default detached

`configure_musia_governance_chain(None)` (the default) preserves v4.14.x
behavior exactly: MUSIA writes go through Φ_agent only. Tenants that
haven't installed a chain see no change.

---

## Test counts

| Suite                                    | v4.14.1 | v4.15.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 693     | 710     |
| governance bridge tests (new)            | n/a     | 17      |

The 17 new tests cover:
- Empty chain is permissive
- Single-pass guard returns True
- Single-deny guard returns False with blocking guard name in reason
- Bridge populates `tenant_id` correctly
- Bridge populates `authenticated_subject` from Authority
- Bridge populates construct type/tier/operation
- Guard exception → defensive denial (no propagation)
- `configure_*` install/uninstall roundtrip
- `installed_validator_or_none()` returns None when detached
- `installed_validator_or_none()` returns working callable when attached
- HTTP write passes when chain detached
- HTTP write passes when chain allows
- HTTP write blocked (403) when chain denies
- Blocked write does not register the construct
- Chain runs alongside quota — quota fires first when both would block (cheaper check)
- Construct-type-specific guards (block boundary, allow state)
- First-failure-stops semantics carry through to MUSIA

The `test_phi_gov_rejects_when_external_validator_blocks` test was updated
(1-line change) to assert on the new specific-reason contract instead of
the old generic-count contract.

Doc/code consistency check passes.

---

## Compatibility

- All v4.14.1 endpoints unchanged in URL or shape
- Chain integration is opt-in via `configure_musia_governance_chain()`
- When detached (default), MUSIA write path is identical to v4.14.x
- `Judgment.reason` now carries specific rejection reasons; clients that read by-key are unaffected
- All 693 v4.14.1 MUSIA tests still pass after the phi_gov test update (1 test, semantic-equivalent change)

---

## Production deployment guidance

### Wiring an existing chain

```python
# At startup, after configuring the existing chain
from mcoi_runtime.app.routers.musia_governance_bridge import (
    configure_musia_governance_chain,
)

# Build the chain as you would for the existing /v1/* routes
chain = build_my_governance_chain()  # rate_limit + budget + jwt + rbac

# Now also gate MUSIA writes
configure_musia_governance_chain(chain)
```

### One chain or two

Most deployments will share a single chain across `/v1/*` and `/constructs/*`.
The bridge populates the chain's GuardContext with MUSIA-aware fields so
the same guards work for both. If a deployment wants different policy
for MUSIA writes vs. legacy endpoints, they can build a second chain and
register it via the bridge while the original chain continues to gate
the legacy paths.

### Guard ordering

Recommended order (cheap → expensive, then MUSIA-specific):

1. `rate_limit` — single hashtable lookup
2. `budget` — small DB read or cached lookup
3. `jwt` / `api_key` — already done by MUSIA's own auth resolver, but useful as defense in depth
4. `rbac` — typically requires user→role→scope lookup
5. Custom MUSIA-specific guards (construct_type policy, tier-based authorization)

The chain stops on first failure, so cheap guards first minimizes
wasted work on rejected requests.

---

## What v4.15.0 still does NOT include

- **Per-domain governance** — `/domains/<name>/process` doesn't currently invoke the chain (it's a read-scoped endpoint that doesn't write to the registry). If a deployment wants chain-gated domain runs, a future workstream can add this.
- **Per-guard scope** — the chain's verdict is binary (pass/fail). Future work could let guards influence Φ_agent levels or other dimensions.
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
v4.15.0  Φ_gov ↔ GovernanceGuardChain bridge
```

710 MUSIA tests; 108 docs; six domains over HTTP with full chain
governance; multi-tenant + multi-auth + persistent + scope-enforced +
size-and-rate-bounded + run-traceable + run-cleanable + run-exportable +
paginated + chain-gated.

---

## Honest assessment

v4.15.0 closes the longest-standing integration gap in MUSIA. The
v4.1.0 release notes promised the chain integration; 14 minor releases
later, it lands. The implementation is small (~150 lines including
tests) because the underlying contracts on both sides were stable —
the only work was the bridge translation.

The bigger structural lesson: MUSIA's `external_validators` slot was
designed in v4.1.0 specifically to host this kind of bridge. It sat
empty for 14 releases, but the design held — when the wiring went in,
no contract changes were needed in either MUSIA or the existing chain.
Designing-for-extension paid off.

What it is not, yet: full MUSIA-native guards. The bridge translates
existing guards to MUSIA's signature, which means custom MUSIA-aware
policy (e.g., "audit how many Tier 2 Transformations a tenant creates
per hour") still has to go through the GovernanceGuard wrapper and the
guard-context dict, not directly via Φ_gov primitives. A future release
could add native MUSIA guard helpers, but the current bridge is enough
for the typical case of "I have an existing chain and want it to apply
to MUSIA writes too."

**We recommend:**
- Upgrade in place. v4.15.0 is additive; default-detached preserves v4.14 behavior.
- Wire your existing chain via `configure_musia_governance_chain()` to unify governance.
- Order chain guards cheap → expensive for best rejection latency.

---

## Contributors

Same single architect, same Mullusi project. v4.15.0 closes the v4.1.0
deferred Φ_gov ↔ governance_guard integration after fourteen minor
releases of building everything around it.
