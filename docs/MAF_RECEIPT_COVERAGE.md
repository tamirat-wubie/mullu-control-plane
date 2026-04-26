# MAF Receipt Coverage Specification — v1

**Status:** Honest baseline. This spec documents what's actually true today, not what the platform aspires to.
**Companion documents:** `docs/LEDGER_SPEC.md`, `maf/MAF_BOUNDARY.md`
**Schema version:** `1`

## Purpose

The platform claims a "certifying Rust substrate with transition receipts."
This document is the canonical specification of what that claim **actually
means today**: which operations produce receipts, what those receipts
contain, where they're stored, and — critically — which operations are
**not** certified despite appearing to be governed.

The companion `LEDGER_SPEC.md` made the audit-trail claim externally
verifiable. This spec applies the same discipline to the receipt claim.
The intent is identical: convert a slogan into a system by stating
exactly what's claimed, what's verified, and what's NOT.

## Compliance posture

| Claim | Status |
|-------|--------|
| "Every governance decision produces a transition receipt." | **Conditionally true** — see "Coverage gaps" below. True for 100% of `/api/v1/*` endpoints via middleware. False for 7 gateway webhook endpoints. |
| "Transition receipts are deterministically hashed." | **Verified** — both Rust and Python implementations hash receipt content with SHA-256 in a fixed canonical order. |
| "The Rust MAF substrate certifies the Python control plane." | **NOT a claim today.** Python does not call into Rust. Both sides implement the same protocol independently. Receipts emitted by Python are not (currently) cross-verified by Rust. |
| "Receipts are persisted." | **NOT a claim today.** `ProofBridge._lineage` is an in-memory dict. Service restart loses the lineage. Receipts shipped to clients in HTTP responses are not retained server-side. |
| "Receipts are tamper-evident under hash-chain integrity." | **NOT a claim for receipts.** The audit ledger (LEDGER_SPEC.md) provides hash-chain integrity for audit entries. Individual receipts have a `causal_parent` field but no global verifier exists for receipt chains. |

When citing receipts in compliance documentation, cite the specific
guarantee (deterministic per-request certification with middleware-level
coverage) — not "certifying Rust substrate." The Rust certification is
architecturally correct but operationally inactive.

## Receipt taxonomy

The platform has **one** receipt structure: `TransitionReceipt`. There is
no `ReceiptKind` enum. Differentiation between receipt types is achieved
by the `verdict` field, which takes one of four values:

### `TransitionVerdict` (Rust: `maf-kernel/src/lib.rs`; Python: `mcoi_runtime/contracts/proof.py`)

| Verdict | Meaning | Typical cause |
|---------|---------|---------------|
| `Allowed` | All guards passed; transition was certified. | Successful governed operation. |
| `DeniedGuardFailed` | One or more guards rejected the transition. | Policy violation, budget exhaustion, RBAC denial. |
| `DeniedIllegalTransition` | The requested state transition is not in the state machine spec. | Logic bug or attempted bypass. |
| `Error` | An exception occurred during evaluation. | Engine fault. Treated as deny by default. |

### `TransitionReceipt` content (v1)

| Field | Description |
|-------|-------------|
| `receipt_id` | Stable opaque ID. |
| `machine_id` | State machine the transition belongs to. |
| `entity_id` | Entity whose state changed (tenant, session, etc.). |
| `from_state` / `to_state` | The transition. |
| `action` | The action that triggered the transition. |
| `before_state_hash` / `after_state_hash` | SHA-256 hashes of pre/post state. |
| `guard_verdicts` | Ordered list of `GuardVerdict { name, passed, reason }`. |
| `verdict` | Overall `TransitionVerdict` (see table above). |
| `replay_token` | Deterministic token for re-execution validation. |
| `causal_parent` | `receipt_id` of the prior receipt in the same lineage (or empty for genesis). |
| `issued_at` | ISO-8601 timestamp. |
| `receipt_hash` | SHA-256 of canonical content. Deterministic. |

### Companion structures

- **`GuardVerdict`** — per-guard pass/fail with a short reason. Always emitted in order, deterministic per request.
- **`CausalLineage`** — chain of `(receipt_id, causal_parent)` pairs maintained per entity. In-memory only.
- **`ProofCapsule`** — bundles `TransitionReceipt + TransitionAuditRecord + lineage_depth`. The unit returned to callers.

## Receipt emission points

### Rust side — `maf-kernel/src/lib.rs`

- `StateMachineSpec::certify_transition()` (one entry point). Constructs receipts. Returns `Result<ProofCapsule>`. **No callers from Python today.**

### Python side — `mcoi/mcoi_runtime/`

- **Middleware (primary path)** — `app/middleware.py:162-181`: every request matching `/api/v1/*` invokes `ProofBridge.certify_governance_decision()` before the endpoint handler runs.
- **Endpoint-level (secondary path)** — `_certify_action_proof()` helpers in `routers/data.py`, `routers/llm.py`, `routers/tenant.py`, `routers/workflow.py` produce receipts that are returned in HTTP responses. These are **in addition to** the middleware receipt, not a replacement.
- **Session-level** — `core/governed_session.py::_certify_proof()` produces receipts during multi-step session operations.

## Coverage invariant (claimed)

**Every state-mutating operation invoked through the platform's HTTP
surface SHALL produce a `TransitionReceipt` with verdict matching the
operation's outcome.**

This invariant is what the platform's "every action is governed" claim
reduces to. It can be CI-enforced once the verifier is built (out of
scope for this spec — the spec must come first). The verifier would:

1. Enumerate every HTTP route that is not idempotent / read-only.
2. Assert each route either:
   - flows through `GovernanceMiddleware` for `/api/v1/*`, **OR**
   - has a route-local proof-emission call site, **OR**
   - is documented in the "Acknowledged exclusions" section below.
3. Fail merge if a new write-endpoint is added without one of the above.

## Coverage today (verified)

Concrete enumeration as of 2026-04-26 (commit `cce2fbb`):

### Routes covered by `GovernanceMiddleware` (100% of `/api/v1/*`)

103 state-mutating endpoints across 21 router modules. Every one of
these flows through `app/middleware.py:162-181`, which invokes
`ProofBridge.certify_governance_decision()` regardless of the route's
implementation. Routes are listed in the audit report at
`docs/audits/maf_receipt_coverage_audit_2026_04_26.md` (to be added).

### Routes with additional endpoint-level receipt emission

Four router modules emit receipts in their handlers and return them in
the response body:

- `routers/data.py` — data-governance actions
- `routers/llm.py` — LLM completion actions
- `routers/tenant.py` — tenant lifecycle actions
- `routers/workflow.py` — workflow execution actions

These receipts are richer than the middleware receipt (they include
domain-specific guard verdicts) and are intended for downstream
consumers that need per-action proof.

### Routes NOT covered (acknowledged gap)

The gateway webhook surface in `gateway/server.py` bypasses
`GovernanceMiddleware` entirely. Seven endpoints are affected:

| Endpoint | Receipt status |
|----------|----------------|
| `POST /webhook/whatsapp` | Not certified at the webhook layer. |
| `POST /webhook/telegram` | Not certified at the webhook layer. |
| `POST /webhook/slack` | Not certified at the webhook layer. |
| `POST /webhook/discord` | Not certified at the webhook layer. |
| `POST /webhook/web` | Not certified at the webhook layer. |
| `POST /webhook/approve/{request_id}` | Not certified at the webhook layer. |
| `POST /authority/approval-chains/expire-overdue` | Not certified at the webhook layer. |

These webhooks **may** trigger downstream `/api/v1/*` calls that are
certified, in which case the certification happens at the secondary
call site, not at the webhook itself. But the webhook receipt itself —
the certification that "this external request was admitted into the
governed plane" — does not exist.

**Implication:** the entry-point trust boundary is not certified on the
webhook surface. An attacker who can deliver a forged webhook payload
that nevertheless validates at the channel level (e.g., HMAC-correct
but semantically forged) gets one un-certified entry into the system.
Downstream operations are still certified, so the damage is bounded —
but the boundary itself is opaque to receipt verification.

## What this spec does NOT claim

These are **not** claims the platform makes today. Listing them
explicitly so compliance reviewers don't infer them.

### 1. Rust certifies Python

Python implements the receipt protocol in `mcoi_runtime/contracts/proof.py`
and `mcoi_runtime/core/proof_bridge.py`. The Rust crates in
`maf/rust/crates/maf-kernel/` implement the same protocol independently.
There is no FFI, no subprocess invocation, no network call from Python
into Rust. Both implementations are kept in lockstep by code review and
by the determinism property (same input → same receipt hash).

A future architectural shift could route Python receipt emission
through Rust for a stronger isolation boundary. That work is **not
done** and is not represented as done.

### 2. Receipts are persisted

`ProofBridge._lineage` is an in-memory `dict[str, CausalLineage]`.
Service restart drops it. Receipts shipped in HTTP responses are not
retained server-side. The only persistent record of a governance
decision is the audit-trail entry in `AuditTrail` (which is in-memory
unless an `AuditStore` is wired and which is itself separate from the
receipt — see LEDGER_SPEC.md).

A future durable receipt store could be added (e.g., PostgreSQL append
table, or by hashing receipts into the audit ledger). Until then,
clients must persist their own receipt copies if they need them.

### 3. Receipts are externally verifiable

There is no `mcoi verify-receipt` analogue of `mcoi verify-ledger`. A
client who receives a receipt in an HTTP response cannot, today, run a
local verifier to confirm the receipt is internally consistent or that
its `causal_parent` chains to a known prior receipt.

A future verifier would mirror the LEDGER_SPEC pattern: pure function,
CLI tool, exit-code discipline, nightly drill. The spec for it does
not yet exist.

### 4. Receipts capture the full state

`before_state_hash` / `after_state_hash` are SHA-256 of structured
state fragments, not full state snapshots. Two transitions with
identical hash-relevant content produce identical hashes regardless of
fields excluded from canonical hashing. The canonical state-hash layout
should be specified the same way LEDGER_SPEC.md specifies entry-hash
content; this is a follow-up document.

## Known gaps (issue-tracker-ready)

| Gap | Severity | Resolution path |
|-----|----------|-----------------|
| Gateway webhooks bypass receipt emission | High | Add a receipt-emission decorator or middleware-equivalent for `gateway/server.py` routes. |
| Receipts not persisted | High | Add `ReceiptStore` protocol mirroring `AuditStore`; wire to PostgreSQL in production profile. |
| No external receipt verifier | Medium | After persistence: implement `mcoi verify-receipt-chain` mirroring `mcoi verify-ledger`. |
| Rust ↔ Python protocol drift caught only by code review | Medium | Add a contract test that both implementations produce the same `receipt_hash` for the same input. |
| State-hash content layout undocumented | Medium | Write `STATE_HASH_SPEC.md` mirroring the entry-hash section of LEDGER_SPEC.md. |
| Coverage invariant not CI-enforced | Medium | After this spec stabilizes: add `scripts/validate_receipt_coverage.py` enumerating routes and asserting each has a known emission path or is in the "Acknowledged exclusions" list. |

These are real gaps, not aspirational items. Each has a defined
resolution path and a severity rating. The platform's claims should
not exceed what this spec establishes as actually true today.

## Versioning

This spec is version `1`. It documents the receipt protocol as
implemented in commit `cce2fbb` (2026-04-26). Schema changes to
`TransitionReceipt` content fields require a new spec version.

A future `MAX_RECEIPT_SPEC_VERSION` constant should be added to the
codebase (parallel to `LEDGER_SCHEMA_VERSION_MAX`) once a verifier
exists that reads `schema_version` from receipts.

## Why this document exists

The audit-trail integrity claim was a slogan until `LEDGER_SPEC.md`
made it a system. The receipt claim is in the same condition today:
architecturally present, partially implemented, and described in the
README in language stronger than the code can support.

This document doesn't add code. It documents what code already does
and — more importantly — what it doesn't do. That distinction is the
difference between a system that earns its compliance posture and one
that asserts it.

The next move from here is not more architecture. It is:

1. Closing the gateway webhook gap (concrete code change).
2. Adding receipt persistence (concrete code change).
3. Building the external verifier (concrete code change).
4. CI-enforcing the coverage invariant (concrete code change).

Each of these is half a day to a week of work. Together they convert
the receipt claim into the same load-bearing artifact the audit ledger
became. Until then, the spec is the contract, and the contract is honest.
