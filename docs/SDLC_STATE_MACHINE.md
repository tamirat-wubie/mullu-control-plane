# SDLC State Machine

Purpose: define allowed software-delivery lifecycle states and transition evidence.
Governance scope: OCE named states, RAG transition links, CDCV evidence-bound movement, CQTE decidable blockers, UWMA transition receipts, and PRS terminal closure.
Dependencies: `docs/SDLC.md`, `schemas/sdlc_closure_receipt.schema.json`, and `scripts/validate_sdlc_state_machine.py`.
Invariants: no transition is valid without required evidence and receipts; terminal states have no outgoing transitions.

## Active States

```text
proposed
triaged
requirements_defined
design_ready
planned
implementation_active
verification_active
security_review
release_candidate
deployment_candidate
deployed
monitored
closed
```

## Blocked States

```text
blocked_requirements
blocked_design
blocked_verification
blocked_security
blocked_release
blocked_deployment
blocked_runtime
```

## Terminal States

```text
closed_success
closed_rejected
closed_superseded
closed_rolled_back
closed_failed_with_receipt
```

## Canonical Progression

```text
proposed -> triaged -> requirements_defined -> design_ready -> planned
-> implementation_active -> verification_active -> security_review
-> release_candidate -> deployment_candidate -> deployed -> monitored
-> closed -> closed_success
```

## Transition Rule

```text
transition_allowed(s1 -> s2)
<=> required_evidence(s2) exists
and required_receipts(s2) exist
and unresolved_blockers(s2) = empty
```

The validator rejects unknown states, missing required transitions, terminal outgoing transitions, blocked states without reason codes, and closure that lacks receipt evidence.
