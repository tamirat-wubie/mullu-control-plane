<!--
Purpose: define the Foundation Mode cost and budget boundary before any spending, paid infrastructure activation, provider billing, payment-method binding, subscription creation, purchase approval, invoice payment, external vendor commitment, or deployment claim.
Governance scope: cost posture, budget posture, paid-infrastructure posture, provider-billing posture, no spending, no payment method, no subscription, no purchase approval, no invoice payment, no vendor commitment, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_cost_budget_witness.awaiting_evidence.json, scripts/validate_foundation_cost_budget_boundary.py.
Invariants: no spending authorization, no paid infrastructure activation, no provider billing activation, no payment-method binding, no subscription creation, no purchase approval, no invoice payment, no approved budget limit, no approved cost forecast, no external vendor commitment, no deployment claim.
-->

# Foundation Cost Budget Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** cost and budget preparation means drafting the categories,
> questions, and approval rules needed before spending starts. It does not
> authorize spending, paid infrastructure, provider billing, payment methods,
> subscriptions, purchases, invoice payments, vendor commitments, or deployment.

Witness packet: [`../examples/foundation_cost_budget_witness.awaiting_evidence.json`](../examples/foundation_cost_budget_witness.awaiting_evidence.json)

Rule: Cost/budget preparation is a local planning boundary, not permission to spend money.

No spending authorization, paid infrastructure activation, provider billing
activation, payment-method binding, subscription creation, purchase approval,
invoice payment, budget-limit approval, cost-forecast approval, external vendor
commitment, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode has many future external dependencies. Even small paid services
can create recurring cost, lock-in, account exposure, and support pressure.
This boundary lets the project prepare cost questions without creating an
expense or payment obligation.

This boundary keeps the work small:

1. Draft cost categories locally.
2. Draft budget, approval, billing, subscription, and purchase questions
   locally.
3. Keep payment methods, vendor account identifiers, invoice records, and
   monetary amounts out of the repository.
4. Keep paid infrastructure and vendor commitments in `AwaitingEvidence`.

## Current State

```text
cost_budget_boundary_state=AwaitingEvidence
spending_allowed=false
paid_infrastructure_allowed=false
provider_billing_allowed=false
payment_method_binding_allowed=false
subscription_creation_allowed=false
purchase_approval_allowed=false
invoice_payment_allowed=false
budget_limit_approved=false
cost_forecast_approved=false
external_vendor_commitment_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not store or claim here |
| --- | --- | --- |
| Expense category draft | Category labels only. | Monetary amounts, vendor quotes, or payment records. |
| Budget limit questions | Approval questions only. | Approved limits or spend authority. |
| Paid infrastructure questions | Service-type questions only. | Active paid hosts, databases, or accounts. |
| Provider billing questions | Billing-risk questions only. | Provider account IDs or billing activation. |
| Payment method questions | Review questions only. | Card, bank, wallet, or payment-method references. |
| Subscription purchase questions | Purchase-flow questions only. | Active subscriptions or purchase approvals. |
| Invoice payment questions | Payment-control questions only. | Invoice records, payment dispatch, or settlement claim. |
| Cost monitoring checklist | Local checklist only. | Live metering, budget approval, or cost forecast approval. |

## Operator Procedure

1. Keep cost/budget materials as local drafts.
2. Do not enter payment methods, start subscriptions, enable billing, or activate
   paid infrastructure in Foundation Mode.
3. Do not record monetary amounts, provider account IDs, invoice records, card
   details, bank details, or payment-method references in public artifacts.
4. Do not approve purchases or invoice payments without later private authority
   evidence and a signed witness.
5. Treat every cost/budget surface as `AwaitingEvidence` until a later witness
   promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_cost_budget_boundary.py
```

The validator checks that the witness packet:

1. keeps every cost/budget surface in `AwaitingEvidence`;
2. blocks spending, paid infrastructure, billing, payment methods,
   subscriptions, purchases, invoice payments, vendor commitments, and
   deployment;
3. rejects URL, email, private-path, payment-shaped, amount-shaped,
   account-shaped, invoice-shaped, or secret-shaped values; and
4. rejects cost/budget readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare secrets/credentials safely | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: spending blocked, paid infrastructure blocked, provider billing blocked, payment-method binding blocked, subscription creation blocked, purchase approval blocked, invoice payment blocked, budget approval blocked, cost forecast approval blocked, vendor commitment blocked, deployment blocked
  Open issues: private spending authority, provider billing review, payment-method review, subscription review, purchase approval, invoice-payment approval, cost forecast, and deployment evidence remain AwaitingEvidence
  Next action: run the cost/budget boundary validator, then keep all spending and paid-service activation closed until evidence promotes it
