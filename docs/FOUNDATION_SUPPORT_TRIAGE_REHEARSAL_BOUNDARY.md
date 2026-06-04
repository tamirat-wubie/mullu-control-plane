<!--
Purpose: define the Foundation Mode support triage rehearsal boundary for public-safe dry-run planning without opening support, accepting requests, handling customer data, or making response commitments.
Governance scope: support triage rehearsal planning, local sample categorization, public-safe issue-shape notes, inbox/routing exclusion, customer-data exclusion, response-commitment blocking, support-tool blocking, onboarding blocking, paid-support blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, examples/foundation_support_triage_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_support_triage_rehearsal_boundary.py.
Invariants: no support triage execution claim, no customer support opening, no inbound message acceptance, no support ticket creation, no inbox routing, no customer-data handling, no personal-data handling, no response-time promise, no SLA claim, no incident-response readiness claim, no support-tool activation, no onboarding, no paid support, and no deployment claim.
-->

# Foundation Support Triage Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** support triage rehearsal preparation means drafting how
> future support requests might be classified, routed, paused, and closed using
> fictional local examples. It does not open support, accept inbound messages,
> create tickets, route inboxes, handle customer or personal data, promise
> response times, claim an SLA, prove incident-response readiness, activate
> support tools, onboard users, sell paid support, or deploy anything.

Witness packet: [`../examples/foundation_support_triage_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_support_triage_rehearsal_witness.awaiting_evidence.json)

Rule: Support triage rehearsal is a local paper exercise, not a customer-support
service or support-readiness proof.

No support triage execution, customer support opening, inbound message
acceptance, support ticket creation, inbox routing, customer-data handling,
personal-data handling, response-time promise, SLA claim, incident-response
readiness claim, support-tool activation, onboarding, paid support, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Support readiness stays closed, but a solo operator still needs a safe way to
think through future support categories before customers exist. This boundary
allows local rehearsal of the shape only.

This is preparation only:

1. Use fictional local examples, not real customer messages.
2. Classify request shapes without opening an inbox or support queue.
3. Define stop rules for privacy, legal, billing, safety, and deployment
   boundaries.
4. Keep every support surface in `AwaitingEvidence`.
5. Do not claim operational support readiness from this rehearsal.

## Current State

```text
support_triage_rehearsal_boundary_state=AwaitingEvidence
support_triage_executed=false
customer_support_open=false
inbound_message_acceptance_allowed=false
support_ticket_creation_allowed=false
inbox_routing_allowed=false
customer_data_handling_allowed=false
personal_data_handling_allowed=false
response_time_promise_claimed=false
support_sla_claimed=false
incident_response_ready_claimed=false
support_tool_activation_allowed=false
onboarding_allowed=false
paid_support_allowed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Fictional request categories | Draft generic request categories. | Do not use real customer messages or personal data. |
| Severity labels | Draft local severity labels. | Do not claim incident-response readiness or on-call coverage. |
| Triage decision rules | Draft when to answer, defer, block, or escalate later. | Do not accept inbound messages or create tickets. |
| Privacy stop rule | Define when support work would touch personal data. | Do not collect, store, or process personal data. |
| Billing stop rule | Define when a request would cross payment or refund boundaries. | Do not move money or offer paid support. |
| Legal stop rule | Define when qualified review would be needed. | Do not give legal conclusions or terms commitments. |
| Tooling stop rule | Define when support tooling would be needed. | Do not activate helpdesk tools, inbox routing, or service accounts. |
| Handoff note | Draft what future support evidence would require. | Do not claim support readiness, SLA, customer access, or deployment. |

## Operator Procedure

1. Keep examples fictional and public-safe.
2. Do not record real inbox content, customer identities, account values,
   ticket IDs, routing targets, or personal data.
3. Treat every support triage rehearsal surface as `AwaitingEvidence`.
4. Stop immediately if work requires support-tool activation, mailbox routing,
   customer contact, payment/refund handling, legal conclusions, personal data,
   incident response, customer access, or deployment.
5. Use the result only as a draft for future support design.

## Validation

Run:

```powershell
python scripts/validate_foundation_support_triage_rehearsal_boundary.py
```

The validator checks that the support triage rehearsal witness:

1. keeps triage execution, support opening, inbound message acceptance, ticket
   creation, inbox routing, customer-data handling, personal-data handling,
   response-time promises, SLA claims, incident-response readiness, support-tool
   activation, onboarding, paid support, and deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. rejects URL, email, private path, inbox, routing, ticket, customer, personal,
   SLA, response-window, billing, legal, support-tool, onboarding, and
   deployment-shaped values; and
4. rejects promotion phrases that imply support, triage, incident, SLA, mailbox,
   onboarding, paid-support, customer-access, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare support readiness safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare customer access without opening access | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: support triage execution blocked, customer support closed, inbound messages blocked, ticket creation blocked, inbox routing blocked, customer-data handling blocked, personal-data handling blocked, response-time promises blocked, SLA claim blocked, incident-response readiness blocked, support-tool activation blocked, onboarding blocked, paid support blocked, deployment blocked
  Open issues: fictional-category evidence, severity-label evidence, triage-rule evidence, privacy-stop evidence, billing-stop evidence, legal-stop evidence, tooling-stop evidence, and handoff evidence remain AwaitingEvidence
  Next action: run the support triage rehearsal validator before relying on support-triage planning as evidence
