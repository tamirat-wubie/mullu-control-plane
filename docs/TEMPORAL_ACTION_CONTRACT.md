# Temporal Action Contract

Purpose: define the governed request-body contract that carries temporal policy
state from an HTTP boundary into the runtime guard chain.
Governance scope: request admission, temporal policy, audit witness, and
pre-dispatch blocking.
Dependencies: `GovernanceMiddleware`, `create_temporal_guard`,
`TemporalRuntimeEngine`, and `TemporalActionRequest`.
Invariants:
- Runtime time is authoritative.
- Invalid temporal action payloads fail closed.
- Temporal policy runs before rate-limit and budget guards in the standard chain.
- Endpoint logic does not execute when temporal policy denies, defers, or escalates.
- Temporal guard details are preserved in decision logs and proof receipts.

## Contract Shape

Governed JSON requests may include a top-level `temporal_action` object:

```json
{
  "temporal_action": {
    "action_id": "act-001",
    "tenant_id": "tenant-a",
    "actor_id": "user-a",
    "action_type": "payment",
    "risk": "high",
    "requested_at": "2026-05-04T13:00:00+00:00",
    "execute_at": "2026-05-04T14:00:00+00:00",
    "expires_at": "2026-05-04T15:00:00+00:00",
    "approval_expires_at": "2026-05-04T15:00:00+00:00",
    "evidence_fresh_until": "2026-05-04T14:30:00+00:00",
    "retry_after": "2026-05-04T13:10:00+00:00",
    "max_attempts": 3,
    "attempt_count": 1
  }
}
```

## Runtime Flow

1. `GovernanceMiddleware` reads governed JSON request bodies.
2. `_extract_temporal_action_field` converts valid payloads into
   `TemporalActionRequest`.
3. Invalid payloads are preserved as raw values.
4. `create_temporal_guard` calls `TemporalRuntimeEngine.decide_temporal_action`.
5. Only `allow` proceeds. `deny`, `defer`, and `escalate` block before endpoint
   execution.

## Verdict Mapping

| Verdict | Guard result | Cause examples |
| --- | --- | --- |
| `allow` | request proceeds | valid approval, due schedule, fresh evidence |
| `deny` | request blocked | expired command, expired approval, retry attempts exhausted |
| `defer` | request blocked | scheduled for future, retry window not open, not-before window |
| `escalate` | request blocked | stale evidence |

## Proof Trace

The temporal guard writes:

```text
ctx["temporal_decision_id"]
ctx["temporal_policy_verdict"]
```

The temporal runtime emits a `temporal_action_decided` event. This anchors the
causal chain from request boundary to temporal policy decision.

The middleware also forwards the temporal guard detail into the governance
decision log and proof bridge:

```json
{
  "guard_name": "temporal",
  "allowed": false,
  "reason": "approval_expired",
  "detail": {
    "decision_id": "dec-temp-action-...",
    "verdict": "deny"
  }
}
```

This detail appears in:

1. `GovernanceDecision.guards_evaluated[].detail`
2. `GovernanceDecision.to_dict()["guards_evaluated"][].detail`
3. `GovernanceProof.guard_verdicts[].detail`
4. `ProofCapsule.receipt.guard_verdicts[].detail`

## Operator Checks

For a temporal denial, operators should verify:

1. HTTP response has `guard = "temporal"`.
2. HTTP response `error` matches the bounded temporal reason.
3. Decision log guard detail has a `decision_id`.
4. Proof receipt guard detail has the same `decision_id`.
5. The endpoint did not execute when the verdict was `deny`, `defer`, or
   `escalate`.
