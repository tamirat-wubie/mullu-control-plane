# Governance Guard Chain Specification — v1

**Status:** Honest baseline. This spec documents what the chain actually enforces today, including which guards are conditional on bootstrap and configuration.
**Companion documents:** `docs/LEDGER_SPEC.md`, `docs/MAF_RECEIPT_COVERAGE.md`
**Schema version:** `1`

## Purpose

The README historically claimed a "7-Guard Chain" enforcing API key →
JWT → tenant → gating → RBAC → content safety → rate limit → budget.
That was eight guard slots, and the governed HTTP chain now also
includes temporal policy before rate limit and budget. The actual count
still varies by configuration because JWT is conditional.

This document is the canonical specification of:

1. The nine guard slots that compose the HTTP chain.
2. The order in which they evaluate.
3. The failure semantics of each guard.
4. Which guards are mandatory and which become no-ops when their
   underlying engine is None or bootstrap fails.
5. The differences between the HTTP-middleware chain and the per-session
   chain (they are not identical).
6. The known silent-bypass scenarios and what closes them.

The intent is identical to the LEDGER_SPEC and MAF_RECEIPT_COVERAGE
specs: convert a slogan into a system by stating what's claimed, what's
verified, and what's NOT claimed today.

## Compliance posture

| Claim | Status |
|-------|--------|
| "The platform enforces a guard chain on every governed operation." | **Conditionally true** — see "Guard inventory" below. Mandatory guards always run; optional guards run only when their engine is wired. |
| "Failed guards return a deny verdict." | **Verified** — every guard's failure path has been audited and returns `GuardResult(allowed=False, ...)`. |
| "Exceptions inside guards are treated as deny." | **Verified** — `GovernanceGuard.check()` (`governance_guard.py:90-98`) catches exceptions and returns deny. |
| "The chain short-circuits on first failure." | **Verified** — `governance_guard.py:150-156`. No subsequent guard runs after the first deny. |
| "All nine guard slots run in pilot/production." | **Conditionally true.** API key, tenant, tenant gating, RBAC, content safety, temporal policy, rate limit, and budget are wired by default; JWT is present when a JWT authenticator is configured. |
| "The HTTP and session chains enforce the same guards in the same order." | **NOT a claim today.** They overlap but differ — see "Two chains" below. |
| "API authentication is required in pilot/production." | **Verified** — `MULLU_API_AUTH_REQUIRED` defaults to True when `MULLU_ENV ∈ {pilot, production}` (`server_services.py:348-350`). |
| "RBAC denial is fail-closed even if the RBAC engine errors." | **Verified** for the runtime path — `governance_guard.py:394-407` catches and returns deny. |
| "RBAC bootstrap failure is fail-closed in pilot/production." | **Verified (this spec, G4.1)** — `Platform.from_env()` now raises `RuntimeError` if `access_runtime` is None when `MULLU_ENV ∈ {pilot, production}`. Was previously a silent no-op. |

## Guard inventory

Nine guard slots. Mandatory means "always added to the chain". Optional
means "added only if its underlying engine is non-None". Optional
guards become silent no-ops when their engine is None — this is the
class of silent bypass G4.1 closes for the RBAC engine.

### 1. API Key (`api_key`)

| Field | Value |
|-------|-------|
| Implementation | `governance_guard.py:281-336` |
| Chain insertion | `server_services.py:351` (inserted at position 0 post-assembly) |
| Mandatory? | **Mandatory** in pilot/production (`require_auth=True`), optional in local_dev/test |
| Failure semantics | Returns `GuardResult(allowed=False, reason="api_key.{denied,missing,inactive,expired}")` |
| Engine | `APIKeyManager` (always created) |
| Bypass conditions | If `require_auth=False`, requests without an Authorization header pass through (dev convenience) |

### 2. JWT (`jwt`)

| Field | Value |
|-------|-------|
| Implementation | `governance_guard.py:234-278` |
| Chain insertion | `middleware.py:266` (conditional: if `jwt_authenticator is not None`) |
| Mandatory? | **Optional** — added only if a JWT authenticator is configured |
| Failure semantics | Returns `GuardResult(allowed=False, reason="jwt.invalid")` on signature/claims failure |
| Engine | `JWTAuthenticator` (configured via `MULLU_JWT_*` env vars) |
| Bypass conditions | If JWT authenticator is None, guard is not in the chain (no-op). API key guard still enforces auth in pilot/production. |

### 3. Tenant Format (`tenant`)

| Field | Value |
|-------|-------|
| Implementation | `governance_guard.py:221-231` |
| Chain insertion | `middleware.py:267` (always added) |
| Mandatory? | **Mandatory** |
| Failure semantics | Returns deny if `tenant_id` is longer than 128 characters |
| Engine | None (pure function) |
| Bypass conditions | This is a **format guard**, not an authorization guard. An empty `tenant_id` passes. |

### 4. Tenant Gating (`tenant_gating`)

| Field | Value |
|-------|-------|
| Implementation | `tenant_gating.py` (`create_tenant_gating_guard`) |
| Chain insertion | `middleware.py:268-270` (conditional: if `tenant_gating_registry is not None`) |
| Mandatory? | **Effectively mandatory** — `Platform.from_env()` always creates the registry; conditional check is defensive |
| Failure semantics | Returns deny if `registry.denial_reason(tenant_id)` is non-None (suspended / terminated tenants) |
| Engine | `TenantGatingRegistry` |
| Bypass conditions | If `tenant_gating_registry is None`, guard is skipped. Currently this never happens in practice — registry construction is outside any try/except. |

### 5. RBAC (`rbac`)

| Field | Value |
|-------|-------|
| Implementation | `governance_guard.py:339-413` |
| Chain insertion | `middleware.py:271-272` (conditional: if `access_runtime is not None`) |
| Mandatory? | **Now mandatory in pilot/production (G4.1).** Was previously optional with silent bypass. |
| Failure semantics | Deny on `decision == DENIED` or `REQUIRES_APPROVAL`; deny on evaluation exception (caught at line 394-407, fail-closed) |
| Engine | `AccessRuntimeEngine` |
| Bypass conditions (pre-G4.1) | If `AccessRuntimeEngine.__init__` raised at bootstrap, `access_runtime = None`, guard skipped, platform continued running with a warning. **This is the silent-bypass HIGH-severity finding.** |
| Bypass conditions (post-G4.1) | `Platform.from_env()` raises `RuntimeError` when `MULLU_ENV ∈ {pilot, production}` and bootstrap fails. Local_dev / test still permits None for development convenience. |

### 6. Content Safety / Λ_input_safety (`content_safety`)

| Field | Value |
|-------|-------|
| Implementation | `content_safety.py` (`create_input_safety_guard`) |
| Chain insertion | `middleware.py:273-274` (conditional: if `content_safety_chain is not None`) |
| Mandatory? | **Effectively mandatory** — `Platform.from_env()` always calls `build_default_safety_chain()`. If it raises, the whole bootstrap fails (no silent path). |
| Failure semantics | Deny if any filter in the chain returns `verdict == "blocked"` for the input |
| Engine | `ContentSafetyChain` (built from `build_default_safety_chain()`) |
| Bypass conditions | Empty content (zero bytes) is skipped — guards only inspect non-empty payloads. This is by design. |

### 7. Temporal Policy (`temporal`)

| Field | Value |
|-------|-------|
| Implementation | `chain.py` (`create_temporal_guard`) |
| Chain insertion | `middleware.py` (conditional: if `temporal_runtime is not None`) |
| Mandatory? | **Effectively mandatory** in the governed server stack — `bootstrap_subsystems()` creates `TemporalRuntimeEngine` and `bootstrap_operational_services()` wires it into `build_guard_chain()` |
| Failure semantics | Deny/defer/escalate verdicts from `TemporalRuntimeEngine.decide_temporal_action()` block admission; invalid temporal action contracts deny fail-closed |
| Engine | `TemporalRuntimeEngine` |
| Bypass conditions | If `temporal_action` is absent, the guard is a no-op. If `temporal_runtime is None`, the guard is skipped; the default server stack wires it. |

### 8. Rate Limit (`rate_limit`)

| Field | Value |
|-------|-------|
| Implementation | `governance_guard.py:167-188` |
| Chain insertion | `middleware.py` (always added after temporal policy) |
| Mandatory? | **Mandatory** |
| Failure semantics | Deny if `rate_limiter.check()` returns `allowed=False` (token bucket exhausted) |
| Engine | `RateLimiter` (dual-gate: tenant + identity) |
| Bypass conditions | None at the chain level. A misconfigured RateLimiter with infinite limits would let everything through, but this is a misconfiguration not a bypass. |

### 9. Budget (`budget`)

| Field | Value |
|-------|-------|
| Implementation | `governance_guard.py:191-218` |
| Chain insertion | `middleware.py` (always added after rate limit) |
| Mandatory? | **Mandatory** |
| Failure semantics | Deny on budget exhaustion or tenant disabled |
| Engine | `TenantBudgetManager` |
| Bypass conditions | If `tenant_id` is empty and `require_tenant=False`, guard passes (system-actor convention). |

## Two chains

The guard chain runs in **two places**, with overlapping but
non-identical guard sets and orders. This is intentional but
understated in the README.

### HTTP-middleware chain (every `/api/v1/*` request)

`mcoi/mcoi_runtime/app/middleware.py:GovernanceMiddleware.dispatch`

```
1. API Key            (mandatory in pilot/prod)
2. JWT                (optional — added if jwt_authenticator wired)
3. Tenant Format      (mandatory)
4. Tenant Gating      (effectively mandatory)
5. RBAC               (mandatory in pilot/prod after G4.1)
6. Content Safety     (effectively mandatory)
7. Temporal Policy    (effectively mandatory)
8. Rate Limit         (mandatory)
9. Budget             (mandatory)
```

### Session-level chain (`GovernedSession.{llm,execute,query}`)

`mcoi/mcoi_runtime/core/governed_session.py`

`session.llm()` order:
```
1. Closed check
2. Session policy            (per-session limits, NOT in HTTP chain)
3. Tenant Gating             (conditional on engine present)
4. RBAC                      (conditional on engine present)
5. Rate Limit                (conditional on engine present)
6. Content Safety (input)    (conditional on engine present)
7. Budget                    (conditional on engine present)
8. LLM call
9. Content Safety (output)   (conditional on engine present, NOT in HTTP chain)
10. PII redaction            (conditional on scanner present, NOT in HTTP chain)
11. Audit record
```

`session.execute()` order:
```
1. Closed check
2. Session policy
3. Tenant Gating
4. RBAC
5. Rate Limit
6. (No content safety — dispatcher handles input/output safety)
7. (No budget charge — dispatcher handles cost accounting)
8. Dispatch
9. Audit record
```

`session.query()` order:
```
1. Closed check
2. Session policy
3. RBAC
4. Rate Limit
5. (No tenant gating, content safety, budget — read-only operation)
6. Audit record
```

**Key differences:**

- Session chain orders RBAC **before** rate limit; HTTP chain orders RBAC **before** content safety which is before rate limit. Different.
- Session chain enforces **session policy** (per-session call limits) which has no HTTP equivalent.
- Session chain enforces **output content safety** and **PII redaction** which have no HTTP equivalent (HTTP chain is pre-dispatch only).
- API Key and JWT do not appear in the session chain — authentication is performed at HTTP entry, then the session inherits the authenticated identity.

## Failure semantics summary

Across both chains, all guards uniformly:

1. **Return** `GuardResult(allowed=False, reason="...")` on policy denial.
2. **Catch** exceptions inside their `check()` and convert to deny (`governance_guard.py:90-98`).
3. **Short-circuit** the chain — no subsequent guard runs.
4. **Record** the denial via the audit trail.
5. **Emit** a transition receipt with `verdict = DeniedGuardFailed` (per `MAF_RECEIPT_COVERAGE.md`).

The chain has no "skip" path. There is no admin override, no
system-actor bypass, no debug flag. System-actor concessions exist
inside individual guards (e.g., empty `tenant_id` may pass the budget
guard) but these are documented per-guard, not chain-wide.

## What this spec does NOT claim

### 1. Guards beyond the nine HTTP guard slots are not covered

`Session policy`, `output content safety`, `PII redaction`, and
`closed-session check` are real enforcement mechanisms but are not
part of the "guard chain" terminology. They run as adjacent checks
inside `GovernedSession`. A future v2 could extend the chain
abstraction to cover them; today they are documented but separate.

### 2. The chain proves admission, not action correctness

Passing the chain means the operation was admitted to the governed
plane. It does not mean the operation completed correctly. Failures
during dispatch (LLM errors, network faults, downstream service
denials) are recorded in the audit trail and the transition receipt
but are not chain failures.

### 3. The chain does not prove tenant isolation

Tenant gating prevents suspended/terminated tenants from acting. It
does not prove that tenant A cannot read tenant B's data — that is a
storage-layer property tested separately (and not yet covered by an
external verifier — see audit gap G5).

### 4. The chain does not authenticate the caller's claimed identity

API Key and JWT guards verify that the request bears a valid token
issued by the platform. They do not verify that the bearer is the
party the token was issued to (impersonation by stolen token is out
of scope for the chain).

## Known gaps (issue-tracker-ready)

| Gap | Severity | Resolution path | Status |
|-----|----------|-----------------|--------|
| RBAC silently bypassed when `access_runtime` bootstrap fails in pilot/production | **High** | Refuse to boot in pilot/production if `access_runtime is None` | **Closed (G4.1, this PR)** |
| README claims "7-Guard Chain" but the HTTP chain has nine guard slots when JWT is configured | Low | README/spec correction | **Closed (G4.0/G4.2)** |
| HTTP and session chains have different orders and different guard sets, which is documented here but not enforced by tests | Medium | Add a test that asserts the canonical order of each chain by name; fail if a future refactor reorders them | Open |
| Output content safety and PII redaction are not in the "chain" abstraction even though they enforce real policy | Low | Spec v2 — extend chain to a generalized notion of "policy checkpoint" covering pre-dispatch, dispatch, and post-dispatch | Open |
| No CI check enumerates `/api/v1/*` routes and asserts each flows through `GovernanceMiddleware` | Medium | Mirror the gap from MAF_RECEIPT_COVERAGE.md — `scripts/validate_guard_chain_coverage.py` | Open |
| No external verifier reads an audit trail and reproves "every entry was preceded by chain admission" | Medium | After ledger persistence and receipt persistence ship: cross-verifier that joins audit + receipt streams | Open |

## Versioning

This spec is version `1`. It documents the guard chain as implemented
in commit `d77b38c` (2026-04-26) plus the changes shipped in the same
PR as this document.

A future spec version will be required if the canonical order of the
HTTP or session chain changes, if guards are added or removed, or if
the failure semantics change.

## Why this document exists

The audit-trail integrity claim was a slogan until `LEDGER_SPEC.md`
made it a system. The receipt claim was a slogan until
`MAF_RECEIPT_COVERAGE.md` made it a system. The guard chain claim
was a slogan until this document.

That completes the pattern across the platform's three load-bearing
governance claims:

| Claim | Spec | Status |
|-------|------|--------|
| Hash-chain audit trail | `LEDGER_SPEC.md` | Load-bearing |
| Transition receipts on every governed action | `MAF_RECEIPT_COVERAGE.md` | Load-bearing |
| Guard chain on every governed operation | `GOVERNANCE_GUARD_CHAIN.md` (this) | Load-bearing |

Each spec includes a compliance posture table that lets a reviewer
distinguish what's verified from what's aspirational. That's the
discipline that keeps "governed" from being a marketing term.

The next moves from here are concrete:

1. Close the medium-severity coverage-CI gap (script that enumerates routes).
2. Ship receipt persistence (carries forward from `MAF_RECEIPT_COVERAGE.md`).
3. Multi-tenant isolation tests (audit gap G5).

These are the work that gets done by shipping, not by auditing the
same artifacts again.
