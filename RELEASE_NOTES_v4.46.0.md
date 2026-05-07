# Mullu Platform v4.46.0 - Temporal Kernel Admission and Proof Witness

**Release date:** TBD
**Codename:** Chronos
**Migration required:** No

---

## What this release is

Adds runtime-owned temporal admission to the governed HTTP chain. Requests can
now carry a `temporal_action` contract, and the platform blocks execution when
approval, evidence, retry, schedule, or expiry constraints are not valid at the
runtime clock.

This release also carries the temporal decision id and verdict into governance
decision logs and proof receipts, so operators can trace the same temporal
decision from request boundary to guard denial to proof capsule.

---

## What is new in v4.46.0

### Temporal action contracts

New temporal contracts define request-time temporal policy state:

- `TemporalClockSample`
- `TemporalActionRequest`
- `TemporalActionDecision`
- `TemporalPolicyVerdict`

The action request supports approval expiry, command expiry, evidence freshness,
future execution, not-before windows, retry windows, and attempt limits.

### Temporal policy engine method

`TemporalRuntimeEngine.decide_temporal_action()` evaluates temporal action
requests against runtime time and returns:

| Verdict | Meaning |
| --- | --- |
| `allow` | Temporal policy permits execution now |
| `deny` | Execution is invalid, such as expired approval or exhausted retries |
| `defer` | Execution is valid later, such as scheduled future execution |
| `escalate` | Execution needs review, such as stale evidence |

### Governance guard chain wiring

The standard HTTP guard chain now supports a `temporal` guard before rate limit
and budget. The guard is inactive when no `temporal_action` is present. When a
temporal action is present, every verdict except `allow` blocks endpoint
execution.

Invalid temporal action payloads fail closed with:

```text
guard = temporal
reason = invalid temporal action
```

### Middleware request boundary extraction

`GovernanceMiddleware` extracts a top-level JSON `temporal_action` object and
converts valid payloads into `TemporalActionRequest`. Invalid shapes are
preserved and passed to the temporal guard so they are rejected explicitly.

### Proof and audit witness

The temporal guard adds bounded detail to its guard result:

```json
{
  "decision_id": "dec-temp-action-...",
  "verdict": "deny"
}
```

That detail is preserved in:

- `GovernanceDecision.guards_evaluated[].detail`
- `GovernanceDecision.to_dict()["guards_evaluated"][].detail`
- `GovernanceProof.guard_verdicts[].detail`
- `ProofCapsule.receipt.guard_verdicts[].detail`

This gives operators a join key from HTTP rejection to temporal decision to
proof receipt.

---

## Documentation

New:

- `docs/TEMPORAL_ACTION_CONTRACT.md`

Updated:

- `docs/GOVERNANCE_GUARD_CHAIN.md`

---

## Test coverage

Focused coverage includes:

- temporal contract validation
- absolute instant comparison across timezone offsets
- approval-expiry boundary behavior
- expired approval denial
- stale evidence escalation
- future schedule deferral
- retry-attempt exhaustion
- temporal guard fail-closed behavior
- middleware request extraction
- endpoint non-execution on temporal denial
- decision-log temporal detail preservation
- proof-receipt temporal detail preservation

Focused verification:

```text
159 passed
```

---

## Operational guidance

Operators investigating a temporal denial should verify:

1. HTTP response has `guard = "temporal"`.
2. HTTP response `error` matches the bounded temporal reason.
3. Decision log guard detail has a `decision_id`.
4. Proof receipt guard detail has the same `decision_id`.
5. Endpoint side effects did not occur for `deny`, `defer`, or `escalate`.

---

## Honest assessment

This release does not implement natural-language time parsing or durable
scheduling. It establishes the governed runtime substrate those higher-level
features require:

- typed temporal action state
- runtime-owned clock decisions
- pre-dispatch temporal admission
- fail-closed invalid payloads
- auditable temporal proof witnesses

That is the necessary first load-bearing layer for reminders, approval expiry,
budget windows, retry windows, stale evidence checks, and schedule-aware
governed operations.
