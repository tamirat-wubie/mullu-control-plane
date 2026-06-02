<!--
Purpose: define the Foundation Mode payment-provider boundary before any provider activation, account binding, merchant onboarding, payment-method collection, live charge, refund, payout, webhook activation, checkout publication, money movement, customer payment access, external publication, or deployment claim.
Governance scope: payment-provider posture, local simulation questions, provider-account blocking, merchant-onboarding blocking, KYC/tax blocking, payment-method blocking, live-money blocking, webhook blocking, checkout blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, examples/foundation_payment_provider_witness.awaiting_evidence.json, scripts/validate_foundation_payment_provider_boundary.py.
Invariants: no payment-provider activation, no provider-account binding, no merchant-onboarding completion claim, no KYC readiness claim, no tax readiness claim, no payment-method collection, no live charge, no refund execution, no payout settlement, no webhook activation, no checkout publication, no money movement, no customer payment access, no external publication, no deployment claim.
-->

# Foundation Payment Provider Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** payment-provider preparation means drafting local questions and
> simulation boundaries for future payment providers. It does not activate a
> provider account, finish merchant onboarding, collect payment methods, process
> a live charge or refund, settle payouts, publish checkout, move money, open
> customer payment access, or deploy.

Witness packet: [`../examples/foundation_payment_provider_witness.awaiting_evidence.json`](../examples/foundation_payment_provider_witness.awaiting_evidence.json)

Rule: Payment-provider preparation is a local planning boundary, not permission
to bind a provider, complete onboarding, collect payment methods, process
payments, settle payouts, publish checkout, move money, open customer payment
access, publish externally, or deploy.

No payment-provider activation, provider-account binding, merchant-onboarding
completion, KYC-readiness, tax-readiness, payment-method collection, live-charge
processing, refund execution, payout settlement, webhook activation, checkout
publication, money movement, customer payment access, external publication, or
deployment claim is permitted by this boundary.

## Why This Exists

Payment providers create legal, financial, privacy, operational, and support
obligations. Foundation Mode can prepare the future control shape, but it must
not cross into live provider setup or money movement. This boundary separates
local simulation from provider activation.

This boundary keeps the work small:

1. Draft provider-selection and account-binding questions locally.
2. Draft merchant-onboarding, KYC, tax, webhook, checkout, charge, refund,
   payout, and reconciliation questions locally.
3. Keep provider account ids, payment method references, transaction ids,
   webhook secrets, endpoint target values, customer identifiers, and monetary
   amounts out of public artifacts.
4. Keep all live payment-provider actions in `AwaitingEvidence`.

## Current State

```text
payment_provider_boundary_state=AwaitingEvidence
payment_provider_activation_allowed=false
provider_account_binding_allowed=false
merchant_onboarding_claimed=false
kyc_readiness_claimed=false
tax_readiness_claimed=false
payment_method_collection_allowed=false
live_charge_allowed=false
refund_execution_allowed=false
payout_settlement_allowed=false
webhook_activation_allowed=false
checkout_publication_allowed=false
money_movement_allowed=false
customer_payment_access_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Payment-Provider Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Provider-selection questions | Draft provider-fit and risk questions. | Do not activate a provider account. |
| Account-binding questions | Draft account-binding prerequisites. | Do not bind provider accounts. |
| Merchant-onboarding questions | Draft onboarding evidence questions. | Do not claim onboarding completion. |
| KYC/tax questions | Draft qualified-review questions. | Do not claim KYC or tax readiness. |
| Payment-method questions | Draft payment-method handling boundaries. | Do not collect cards, banks, wallets, or tokens. |
| Checkout-flow questions | Draft local checkout simulation shape. | Do not publish checkout or payment links. |
| Webhook-event questions | Draft webhook evidence requirements. | Do not activate webhooks or store webhook secrets. |
| Charge/refund questions | Draft live-money stop rules. | Do not process charges or refunds. |
| Payout/settlement questions | Draft settlement evidence questions. | Do not settle payouts. |
| Reconciliation-receipt questions | Draft receipt and ledger questions. | Do not claim payment closure or money movement. |

## Operator Procedure

1. Keep provider work as local questions and simulation-only notes.
2. Do not create, bind, or verify provider accounts in public artifacts.
3. Do not enter payment methods, process live charges, run refunds, settle
   payouts, publish checkout, activate webhooks, or expose payment endpoints.
4. Do not record provider account ids, transaction ids, customer ids, webhook
   secrets, payment-method references, URLs, emails, private paths, or monetary
   amounts in the witness.
5. Treat every payment-provider surface as `AwaitingEvidence` until a later
   private authority witness promotes one exact bounded step.

## Validation

Run:

```powershell
python scripts/validate_foundation_payment_provider_boundary.py
```

The validator checks that the payment-provider witness:

1. keeps every payment-provider surface in `AwaitingEvidence`;
2. blocks provider activation, provider binding, onboarding completion, KYC/tax
   readiness, payment-method collection, live charges, refunds, payouts,
   webhooks, checkout publication, money movement, customer payment access,
   external publication, and deployment;
3. rejects URL, email, private-path, provider-account, transaction,
   payment-method, customer, amount, live-mode, webhook-secret, or secret-shaped
   values; and
4. rejects payment-provider readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See cost and budget boundaries | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| See current claim truth | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |

STATUS:
  Completeness: 100%
  Invariants verified: provider activation blocked, provider account binding blocked, merchant onboarding blocked, KYC readiness blocked, tax readiness blocked, payment-method collection blocked, live charges blocked, refunds blocked, payouts blocked, webhooks blocked, checkout publication blocked, money movement blocked, customer payment access blocked, external publication blocked, deployment blocked
  Open issues: provider selection, account binding, merchant onboarding, KYC/tax review, payment-method handling, checkout flow, webhook evidence, charge/refund controls, payout settlement, reconciliation receipts, customer payment access, and deployment evidence remain AwaitingEvidence
  Next action: run the payment-provider boundary validator, then keep all provider and money-movement actions closed until evidence promotes one exact bounded step
