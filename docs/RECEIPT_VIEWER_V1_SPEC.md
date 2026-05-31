# Receipt Viewer v1 Specification

Purpose: define the first buyer/operator-facing proof surface for governed AI execution.
Governance scope: receipt lookup, admission proof, provider evidence, reconciliation status, closure status, and public-claim-safe display.
Dependencies: `docs/MAF_RECEIPT_COVERAGE.md`, `docs/STATE_HASH_SPEC.md`, `docs/EVIDENCE_CLASSIFICATION.md`, `DEPLOYMENT_STATUS.md`.
Invariants: the viewer may show proof artifacts but may not convert internal consistency into external-world truth unless provider and reconciliation evidence are present.

## Product role

The receipt viewer is the first trust surface. It should answer:

```text
What happened, why was it allowed or denied, which evidence was used, who approved it, what proof was emitted, and whether the outside world matched the expected result?
```

## Receipt tiers

| Tier | Name | Meaning | Display claim |
| --- | --- | --- | --- |
| `R0` | Planned | Intent or plan exists but has not been admitted | planned only |
| `R1` | Internally certified | Governance decision and transition receipt are internally consistent | Mullu admitted/denied/escalated this action |
| `R2` | Provider-confirmed | External provider response is captured and bound to the action | provider accepted/rejected the request |
| `R3` | Reconciled | External state was checked after provider response | observed result matched/mismatched expected state |
| `R4` | Independently auditable | Evidence bundle can be exported and independently reviewed | audit package ready for review |

## Required v1 fields

| Field | Purpose |
| --- | --- |
| `receipt_hash` | Primary lookup key |
| `receipt_id` | Runtime receipt identifier |
| `action_id` | User/task/action identifier when present |
| `tenant_id` | Tenant scope, redacted when viewer lacks authority |
| `actor_id` | Actor, operator, or service identity |
| `channel` | Entry surface such as web, Slack, API, scheduler, or worker |
| `capability_id` | Capability used or requested |
| `risk_class` | Computed action risk |
| `guard_verdicts` | Ordered admission checks |
| `decision` | allowed, denied, deferred, escalated, failed, or closed |
| `evidence_refs` | Evidence used for admission |
| `approval_refs` | Approval evidence when required |
| `provider_receipt_refs` | External provider result evidence when present |
| `reconciliation_refs` | External state verification when present |
| `closure_state` | terminal state when available |
| `receipt_tier` | R0-R4 tier |
| `claim_boundary` | what this receipt can and cannot prove |

## Viewer screens

1. **Receipt summary**: action, decision, tier, time, tenant, capability, risk.
2. **Guard trace**: ordered guard verdicts with reasons.
3. **Evidence panel**: evidence refs, freshness, classification, and allowed claim boundary.
4. **Approval panel**: approval chain, approver, expiry, separation-of-duty status.
5. **Provider panel**: provider response hash/status without leaking secrets or raw payloads.
6. **Reconciliation panel**: observed external state and mismatch/uncertain markers.
7. **Closure panel**: committed, compensated, accepted-risk, requires-review, failed, cancelled, missed, or expired.
8. **Export panel**: evidence bundle export when authorization permits.

## Safety rules

1. Do not display raw secrets, bearer tokens, API keys, authorization headers, or raw provider bodies.
2. Do not label an `R1` receipt as proof that the outside world changed.
3. Do not label fixture evidence as live evidence.
4. Do not show tenant or actor details across tenant boundaries.
5. Do not hide denied or failed guard verdicts.
6. Do not omit stale-evidence warnings.
7. Do not show production-health claims unless `DEPLOYMENT_STATUS.md` and live witness evidence support them.

## v1 API target

```text
GET /api/v1/simple/receipts/{receipt_hash}
GET /api/v1/simple/receipts/{receipt_hash}/bundle
GET /api/v1/simple/proof-demo
```

The initial `proof-demo` route should use fixture or local evidence only and label it as such.

## Market value

A generic dashboard says the system ran. The receipt viewer shows the governance value:

```text
allowed/denied -> because of these guards -> using this evidence -> under this authority -> with this receipt -> bounded by this claim.
```
