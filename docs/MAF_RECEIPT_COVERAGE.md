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
| "Every governance decision produces a transition receipt." | **Verified** for the HTTP entry surface. 100% of `/api/v1/*` endpoints certified via `GovernanceMiddleware`. 100% of gateway `POST /webhook/*`, `POST /authority/*`, `POST /capability-fabric/*`, and `POST /capability-plans/*` recovery endpoints certified via `GatewayReceiptMiddleware` (closed in commit shipping G10.1 and extended for plan recovery and capsule admission). |
| "Transition receipts are deterministically hashed." | **Verified** — both Rust and Python implementations hash receipt content with SHA-256 in a fixed canonical order. Cross-language equality is locked by `maf-kernel::receipt_hash_matches_python_sha256` and `mcoi/tests/test_proof_hash_contract.py`, which both assert against the same hardcoded SHA-256 constant. |
| "The Rust MAF substrate certifies the Python control plane." | **NOT a claim today.** Python does not call into Rust. Both sides implement the same protocol independently. Receipts emitted by Python are not (currently) cross-verified by Rust. |
| "Receipts are persisted." | **Bounded claim only.** Default `ProofBridge` still uses in-memory storage, but `JsonlReceiptStore` provides an append-only durable backend for emitted receipts and lineage when explicitly injected or configured with `MULLU_RECEIPT_STORE_JSONL_PATH`. Production PostgreSQL wiring is still not claimed. |
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
- `routers/llm.py` — model completion actions
- `routers/tenant.py` — tenant lifecycle actions
- `routers/workflow.py` — workflow execution actions

These receipts are richer than the middleware receipt (they include
domain-specific guard verdicts) and are intended for downstream
consumers that need per-action proof.

### Gateway entry-point coverage (G10.1 — closed)

Gateway webhook, authority, capability-fabric, capability-plan recovery,
deployment-authority, and operator-control endpoints are now certified by
`GatewayReceiptMiddleware` in `gateway/receipt_middleware.py`. Every
POST to a `/webhook/*`, `/authority/*`, `/capability-fabric/*`,
`/capability-plans/*`, `/deployment/*`, or `/operator/*` path produces a receipt
regardless of which handler runs:

| Endpoint | Receipt status |
|----------|----------------|
| `POST /webhook/whatsapp` | Certified (G10.1). |
| `POST /webhook/telegram` | Certified (G10.1). |
| `POST /webhook/slack` | Certified (G10.1). |
| `POST /webhook/discord` | Certified (G10.1). |
| `POST /webhook/web` | Certified (G10.1). |
| `POST /webhook/approve/{request_id}` | Certified (G10.1). |
| `POST /authority/approval-chains/expire-overdue` | Certified (G10.1). |
| `POST /authority/obligations/{id}/satisfy` | Certified (G10.1). |
| `POST /authority/obligations/escalate-overdue` | Certified (G10.1). |
| `POST /capability-fabric/capsule-admissions` | Certified (capsule admission extension). |
| `POST /capability-plans/{plan_id}/recover` | Certified (plan recovery extension). |
| `POST /deployment/tenant-mappings` | Certified (deployment authority extension). |
| `POST /operator/goal-intake/preview` | Certified (operator-control extension). |
| `POST /operator/goal-intake/approve` | Certified (operator-control extension). |
| `POST /operator/goal-intake/deny` | Certified (operator-control extension). |
| `POST /operator/current-task/approval` | Certified (operator-control extension). |

The middleware certifies the **boundary decision** (was this request
admitted, denied, or did the handler error?), not the business
decision. Outcome mapping is HTTP-status-driven:

| Status | Decision | Audit outcome |
|--------|----------|---------------|
| 2xx | `allowed` | `success` |
| 4xx | `denied` | `denied` |
| 5xx | `denied` | `error` |
| handler exception (uncaught) | `denied` | `error` (re-raised after receipt) |

The middleware is observability, not a gate: if `proof_bridge` raises
or is None, the gateway continues to function and a warning is logged.
A drift between request-log volume and `proof_bridge.receipt_count` is
the operational signal that something is wrong.

**What the gateway receipt does NOT prove:** the receipt captures the
admission decision, not the legitimacy of the upstream caller. A
channel-level forgery (e.g., HMAC-correct but semantically false
payload) still produces an `allowed` receipt. The HMAC/signature checks
at each handler are the layer that detects forgery; the receipt simply
records what they decided.

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

The default `ProofBridge` store is in-memory and service restart drops
that default state. `JsonlReceiptStore` is the first durable backend:
when explicitly injected or configured through
`MULLU_RECEIPT_STORE_JSONL_PATH`, it persists emitted receipts and
lineage as append-only JSONL events and replays them on startup. The
environment-configured path fails closed during foundation bootstrap if
it contains control characters, points at an existing directory, or
cannot replay an existing JSONL file. Foundation bootstrap enables
JSONL `fsync` by default through `MULLU_RECEIPT_STORE_JSONL_SYNC=true`;
operators may set it to `false` only when they explicitly accept the
weaker local-crash durability profile.

Production database wiring is still not a claim. Until a production
profile wires a database-backed store (e.g., PostgreSQL append table, or
by hashing receipts into the audit ledger), default receipts should be
treated as response-time proof objects rather than production durable
compliance records.

### 3. Receipts prove external transition truth

The `mcoi verify-receipt-chain <input>` verifier now recomputes receipt
hashes, receipt ids, replay tokens, and `causal_parent` linkage for
exported JSON or JSONL receipt chains. A client who receives receipts
can run a local verifier to confirm internal consistency.

This does not prove the external truth of the transition. It proves only
that the exported receipt fields are mutually consistent and chain to
the supplied `genesis` or `--anchor-hash` parent.

### 4. Receipts capture the full state

`before_state_hash` / `after_state_hash` are SHA-256 of structured
state fragments, not full state snapshots. Two transitions with
identical hash-relevant content produce identical hashes regardless of
fields excluded from canonical hashing. The canonical state-hash layout
should be specified the same way LEDGER_SPEC.md specifies entry-hash
content; this is a follow-up document.

## Known gaps (issue-tracker-ready)

| Gap | Severity | Resolution path | Status |
|-----|----------|-----------------|--------|
| Gateway webhooks bypass receipt emission | High | `GatewayReceiptMiddleware` in `gateway/receipt_middleware.py` | **Closed (G10.1)** |
| Receipts not persisted | High | Add `ReceiptStore` protocol mirroring `AuditStore`; wire to PostgreSQL in production profile. | Partially closed — `JsonlReceiptStore` persists emitted receipts and lineage as append-only JSONL when injected into `ProofBridge` or configured through `MULLU_RECEIPT_STORE_JSONL_PATH`; production PostgreSQL profile wiring remains open. |
| No external receipt verifier | Medium | After persistence: implement `mcoi verify-receipt-chain` mirroring `mcoi verify-ledger`. | **Closed** — `mcoi verify-receipt-chain` verifies exported JSON/JSONL receipt chains for receipt hash, receipt id, replay token, and causal-parent linkage. |
| Rust ↔ Python protocol drift caught only by code review | Medium | Add a contract test that both implementations produce the same `receipt_hash` for the same input. | **Closed** — paired tests in `maf-kernel/src/lib.rs` and `mcoi/tests/test_proof_hash_contract.py` pin the canonical content to a hardcoded SHA-256 constant on each side. Drift on either side fails the matching test. |
| State-hash content layout undocumented | Medium | Write `STATE_HASH_SPEC.md` mirroring the entry-hash section of LEDGER_SPEC.md. | **Closed** — `docs/STATE_HASH_SPEC.md` documents the canonical content layout (`state:entity_id:timestamp`), Python `proof_bridge.py::state_hash`, Rust `maf-kernel::state_hash`, the `mcoi verify-state-hash` internal-consistency verifier, and the remaining v2 design gap for structured entity fields. |
| Receipt persistence architectural seam | High | Define a `ReceiptStore` Protocol so a durable backend can plug in without touching ProofBridge core logic. (Separate from picking the durable shape.) | **Closed** — `mcoi/mcoi_runtime/contracts/receipt_store.py` defines `ReceiptStore` (base class with no-op defaults, mirroring AuditStore's pattern), `InMemoryReceiptStore` (default, preserves pre-Protocol FIFO eviction at MAX_LINEAGE_ENTRIES), and `JsonlReceiptStore` (append-only durable receipt + lineage JSONL replay). `ProofBridge` records emitted receipts and lineage through the Protocol via injection. The production storage shape decision (PostgreSQL append table vs ledger-hashed) is still the operator's call, but the architectural blocker is removed. |
| Replay token has no verifier | Low-Medium | Surfaced by audit 2026-04-28: every receipt has a `replay_token` field but no code anywhere consumes it. Field name implies a contract the codebase doesn't honor. | **Closed** — `ProofBridge.verify_replay_token(receipt) -> bool` (static) reconstructs the token from the receipt's content + issued_at and compares. Holds the token-internal-consistency half of replay validation; a real replay system that derives its own token and compares would close the loop. |
| Coverage invariant not CI-enforced | Medium | Add `scripts/validate_receipt_coverage.py` enumerating routes and asserting each has a known emission path or is in the "Acknowledged exclusions" list. | **Closed** — `scripts/validate_receipt_coverage.py` enumerates every state-mutating route and classifies it as MIDDLEWARE_API / MIDDLEWARE_GATEWAY / MIDDLEWARE_MUSIA / EXCLUDED / UNCOVERED. The ratchet test `mcoi/tests/test_receipt_coverage_invariant.py` pins the UNCOVERED count to zero; any drift fails the test, so coverage regressions are reviewer-visible. The script supports `--strict` for CI gating. |
| MUSIA + gateway-internal routes not on the receipt path | High | MUSIA state-mutating routes (`/cognition`, `/constructs`, `/domains`, `/musia/*`, `/ucja`) are classified as covered by `MusiaReceiptMiddleware`. The standalone capability worker route `POST /capability/execute` in `gateway/capability_worker.py` is covered by `GatewayReceiptMiddleware`, installed by `create_capability_worker_app` with a worker-local `ProofBridge` when no platform bridge is supplied. The ratchet test (`mcoi/tests/test_receipt_coverage_invariant.py`) pins the uncovered count to zero. | **Closed** — ratcheted to zero uncovered routes on 2026-05-16 |
| Failed guard verdicts stripped from denied receipts | High | Pre-fix `proof_bridge.py::_certify_locked` filtered failed guards out of the verdict list before calling `certify_transition`, because that function raised on any failed guard. The receipt's `guard_verdicts` field then contained only passing guards — the denial reason was missing from the cryptographic record, and the receipt's `verdict` was always `ALLOWED` even for denied decisions. Fix: `certify_transition` (Python `contracts/proof.py` and Rust `maf-kernel/src/lib.rs`) now produces a receipt with `verdict=DENIED_GUARD_FAILED` and the full guard list when any guard fails (illegal transitions still raise/return Err). The bridge no longer filters. The receipt IS the proof of the denial. | **Closed** — surfaced and fixed 2026-04-28. Tests in `test_proof_substrate.py::test_failed_guard_emits_denied_receipt`, `test_proof_bridge.py::test_failed_guard_verdict`, and the Rust mirror `certify_with_failed_guard_emits_denied_receipt` lock the new behavior. |

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

The remaining move from here is durable production receipt persistence.
Gateway receipt coverage, the external receipt verifier, state-hash
verification, and CI coverage enforcement are now implemented and pinned by
tests. PostgreSQL receipt-store profile wiring remains open; until it lands,
`JsonlReceiptStore` is the durable local receipt path and the spec is the
contract boundary.
