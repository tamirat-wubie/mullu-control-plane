<!--
Purpose: define the Foundation Mode support-readiness boundary before any pilot, customer, onboarding, SLA, or incident-response claim.
Governance scope: support posture, incident-preparation posture, mailbox-label posture, no customer support opening, no SLA claim, no live-response claim, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_support_readiness_witness.awaiting_evidence.json, scripts/validate_foundation_support_readiness_boundary.py.
Invariants: no customer support claim, no support SLA claim, no incident-response readiness claim, no support mailbox deliverability claim, no onboarding claim, no paid-support claim, no deployment claim.
-->

# Foundation Support Readiness Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** support-readiness preparation means writing the support shape
> before anyone depends on it. It does not open customer support, promise a
> response time, verify mailbox delivery, start onboarding, or prove incident
> response readiness.

Witness packet: [`../examples/foundation_support_readiness_witness.awaiting_evidence.json`](../examples/foundation_support_readiness_witness.awaiting_evidence.json)

Rule: Support preparation is a local planning boundary, not a customer-support service.

No customer support opening, support SLA, incident-response readiness, support
mailbox deliverability, onboarding, paid support, customer access, or deployment
claim is permitted by this boundary.

## What This Boundary Solves

Customer or pilot access creates support duties. A solo operator should not
create those duties by accident. Foundation Mode needs a support boundary that
defines what must exist later while keeping the current state closed.

This boundary keeps support preparation small:

1. Public support labels can be named without claiming deliverability.
2. Support triage can be drafted without accepting requests.
3. Incident response can be outlined without claiming operational readiness.
4. Escalation, rollback, and closure expectations can be prepared locally.

## Current State

```text
support_readiness_boundary_state=AwaitingEvidence
customer_support_open=false
support_sla_claimed=false
incident_response_ready_claimed=false
support_mailbox_deliverability_claimed=false
onboarding_allowed=false
live_support_commitment_allowed=false
paid_support_allowed=false
customer_access_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not claim here |
| --- | --- | --- |
| Support mailbox label | Public label only. | Inbox access, routing, delivery, response time. |
| General contact label | Public label only. | Staffed intake or guaranteed response. |
| Triage categories | Draft categories. | Active support queue or customer workflow. |
| Incident runbook | Local outline. | Incident-response readiness or on-call coverage. |
| Rollback contact path | Draft owner-only note. | Live escalation coverage. |
| Closure criteria | Draft checklist. | Operational SLA or legal support duty. |

## Operator Procedure

1. Keep support materials as local drafts.
2. Do not publish support promises or response windows.
3. Do not claim mailbox deliverability until manual evidence exists.
4. Do not open onboarding or intake until terms, privacy, recovery, deployment,
   and legal/business boundaries are promoted by evidence.
5. Treat every support surface as `AwaitingEvidence` until a later signed
   witness promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_support_readiness_boundary.py
```

The validator checks that the witness packet:

1. keeps every support surface in `AwaitingEvidence`;
2. keeps support opening, SLA, incident readiness, onboarding, paid support,
   customer access, and deployment blocked;
3. rejects private inbox, account, secret, or routing-shaped values; and
4. rejects support-readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare product scope safely | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: customer support closed, support SLA not claimed, incident readiness not claimed, mailbox deliverability not claimed, onboarding blocked, paid support blocked, deployment blocked
  Open issues: support workflow evidence, incident runbook evidence, response capacity, mailbox deliverability, onboarding, and legal/business review remain AwaitingEvidence
  Next action: run the support-readiness boundary validator, then keep support surfaces closed until evidence promotes them
