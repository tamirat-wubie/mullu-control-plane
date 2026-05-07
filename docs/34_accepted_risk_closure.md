# 34 - Accepted Risk Closure

## Purpose

Accepted risk is the bounded closure path for unresolved verification or effect
reconciliation gaps. It is not a success state and it is not a substitute for
observed effects. It records that an authorized owner accepts a known residual
risk for a limited time while a review obligation remains active.

The layer answers: what verification gap remains, who accepted it, who owns it,
what evidence supports the decision, when the acceptance expires, what case is
open, and what follow-up obligation must close the gap?

## Owned Artifacts

| Artifact | Role |
|---|---|
| `AcceptedRiskRecord` | Canonical bounded residual-risk admission |
| `AcceptedRiskDecision` | Deterministic admission result for a proposed acceptance |
| `AcceptedRiskLedger` | Runtime store and graph anchor for accepted-risk records |
| Operational graph review node | Reality map node for the acceptance decision |
| Evidence links | Proof references supporting the acceptance |

## Admission Rule

Accepted risk may be admitted only when all of the following are true:

1. The effect reconciliation is unresolved: `partial_match`, `mismatch`, or
   `unknown`.
2. The verification result is absent, failed, or inconclusive.
3. A case exists for the unresolved effect.
4. An owner is assigned.
5. An approver explicitly accepts the bounded risk.
6. At least one evidence reference supports the acceptance.
7. A review obligation exists.
8. `expires_at` is in the future.

Matched reconciliation and passing verification cannot create accepted risk.

## Runtime Behavior

`AcceptedRiskLedger.evaluate_acceptance(...)` returns an
`AcceptedRiskDecision`. It does not mutate the accepted-risk record set.

`AcceptedRiskLedger.accept(...)` creates an active `AcceptedRiskRecord` only
after deterministic admission passes. If an operational graph is attached, the
ledger anchors:

| Node | Type |
|---|---|
| `command:{command_id}` | job |
| `case:{case_id}` | incident |
| `accepted_risk:{risk_id}` | review |
| `person:{owner_id}` | person |
| `obligation:{review_obligation_id}` | job |
| `evidence:{evidence_ref}` | document |

The graph edges bind command, case, review decision, owner, obligation, and
evidence into an auditable causal structure.

## Lifecycle

```text
proposed
  -> active
  -> closed / expired / revoked
```

`expire_due_records()` transitions active records to `expired` when their
review window elapses. Expired accepted risk is no longer an active closure
surface.

`close(risk_id, evidence_ref=...)` closes an active record only when follow-up
evidence is attached.

## Hard Invariants

1. No accepted risk for `MATCH` reconciliation.
2. No accepted risk for passing verification.
3. No accepted risk without case, owner, approver, expiry, obligation, and
   evidence.
4. No unbounded accepted risk.
5. No graph anchor without evidence references.
6. No active accepted risk past expiry.
7. No accepted risk silently resolving the original verification gap.

## Relationship To Effect Assurance

Effect assurance determines whether the actual observed world effects match the
predicted plan. Accepted risk begins only after that comparison is unresolved.
It preserves operational honesty:

```text
MATCH
  -> commit

PARTIAL_MATCH / MISMATCH / UNKNOWN
  -> case
  -> accepted risk only if explicitly bounded
  -> review obligation remains open
```
