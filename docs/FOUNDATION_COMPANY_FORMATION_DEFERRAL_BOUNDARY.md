<!--
Purpose: define the Foundation Mode boundary for deferring company formation, entity registration, tax identifiers, business accounts, payroll, contracts, ownership claims, money movement, customer access, publication, and deployment.
Governance scope: local company-formation deferral, entity-registration blocking, identifier blocking, bank/payment blocking, payroll blocking, contract blocking, investor/equity blocking, accounting/insurance blocking, legal-clearance blocking, money-movement blocking, customer-access blocking, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md, examples/foundation_company_formation_deferral_witness.awaiting_evidence.json, scripts/validate_foundation_company_formation_deferral_boundary.py.
Invariants: no company formation claim, no entity registration, no entity-name reservation, no legal-entity identifier, no tax identifier, no registered-agent record, no business-address record, no business bank account, no payment processor account, no payroll setup, no contractor agreement, no investor agreement, no ownership/equity allocation claim, no accounting readiness claim, no insurance readiness claim, no legal-clearance claim, no money movement, no customer access, no external publication, and no deployment claim.
-->

# Foundation Company Formation Deferral Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** company-formation deferral means recording that no company,
> entity, tax, banking, payroll, contractor, investor, ownership, insurance,
> customer, publication, or deployment authority exists yet. It does not form
> an entity, reserve a name, record identifiers, open accounts, approve
> contracts, move money, invite customers, publish externally, or deploy.

Witness packet: [`../examples/foundation_company_formation_deferral_witness.awaiting_evidence.json`](../examples/foundation_company_formation_deferral_witness.awaiting_evidence.json)

Rule: Company-formation deferral is a local stop-rule packet for future
formation review. It is not legal advice, not company authority, not tax
readiness, not bank readiness, not payment readiness, not contract authority,
not customer authority, and not deployment readiness.

No company formation claim, entity registration, entity-name reservation,
legal-entity identifier, tax identifier, registered-agent record,
business-address record, business bank account, payment processor account,
payroll setup, contractor agreement, investor agreement, ownership/equity
allocation claim, accounting readiness claim, insurance readiness claim,
legal-clearance claim, money movement, customer access, external publication,
or deployment claim is permitted by this boundary.

## What This Boundary Solves

The legal/business and funding/team boundaries block company claims broadly.
This boundary makes the company-formation stop rule explicit enough for a solo
operator who is still pre-entity, pre-tax, pre-bank, pre-payment, pre-team,
pre-customer, and pre-deployment.

Use it when the question is:

1. Which company-formation facts must stay out of Git and public docs?
2. Which future formation gates are only labels today?
3. Which business-account or tax steps are blocked before review?
4. Which ownership, contractor, investor, or payroll claims are unsafe?
5. Which reassessment step must happen before formation work begins?

## Current State

```text
company_formation_deferral_state=AwaitingEvidence
company_formation_claimed=false
entity_registration_allowed=false
entity_name_reserved=false
legal_entity_identifier_recorded=false
tax_identifier_recorded=false
registered_agent_recorded=false
business_address_recorded=false
business_bank_account_allowed=false
payment_processor_account_allowed=false
payroll_setup_allowed=false
contractor_agreement_allowed=false
investor_agreement_allowed=false
ownership_equity_allocation_claimed=false
accounting_readiness_claimed=false
insurance_readiness_claimed=false
legal_clearance_claimed=false
money_movement_allowed=false
customer_access_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Deferral Labels

These labels are stop-rule gates only. They are not entity names, reserved
names, entity identifiers, tax identifiers, registered-agent records,
addresses, bank records, processor records, payroll records, contracts,
investor records, ownership records, timestamps, hashes, private paths,
account identifiers, or deployment receipts.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `formation_scope_gate` | Future formation-scope gate. | Do not claim formation scope closure. |
| `entity_registration_gate` | Future entity-registration gate. | Do not register or claim an entity. |
| `entity_name_reservation_gate` | Future name-reservation gate. | Do not reserve or record an entity name. |
| `legal_entity_identifier_gate` | Future identifier gate. | Do not record legal-entity identifiers. |
| `tax_identifier_gate` | Future tax identifier gate. | Do not record tax identifiers. |
| `registered_agent_address_gate` | Future agent/address gate. | Do not record registered-agent or business-address facts. |
| `business_bank_account_gate` | Future bank-account gate. | Do not open or claim a business bank account. |
| `payment_processor_account_gate` | Future processor-account gate. | Do not activate payment processor accounts. |
| `payroll_setup_gate` | Future payroll gate. | Do not set up payroll. |
| `contractor_agreement_gate` | Future contractor gate. | Do not engage contractors. |
| `investor_agreement_gate` | Future investor gate. | Do not sign investor agreements. |
| `ownership_equity_gate` | Future ownership/equity gate. | Do not claim ownership or equity allocation closure. |
| `accounting_readiness_gate` | Future accounting gate. | Do not claim accounting readiness. |
| `insurance_readiness_gate` | Future insurance gate. | Do not claim insurance readiness. |
| `legal_clearance_gate` | Future legal-clearance gate. | Do not claim legal clearance. |
| `money_movement_gate` | Future money-movement gate. | Do not move money. |
| `customer_access_gate` | Future customer-access gate. | Do not open customer access. |
| `publication_deployment_gate` | Future publication/deployment gate. | Do not publish externally or deploy. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve company-formation promotion. |

## Deferral Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Formation scope | Record the stop-rule label. | Do not claim formation scope closure. |
| Entity registration | Record the stop-rule label. | Do not register or claim an entity. |
| Entity name | Record the stop-rule label. | Do not reserve or record entity names. |
| Entity identifiers | Record the stop-rule label. | Do not record legal-entity identifiers. |
| Tax identifiers | Record the stop-rule label. | Do not record tax identifiers. |
| Agent/address | Record the stop-rule label. | Do not record registered-agent or business-address facts. |
| Business bank account | Record the stop-rule label. | Do not open or claim bank-account readiness. |
| Payment processor account | Record the stop-rule label. | Do not activate payment processing. |
| Payroll | Record the stop-rule label. | Do not set up payroll. |
| Contractor agreement | Record the stop-rule label. | Do not hire, contract, or approve SOWs. |
| Investor agreement | Record the stop-rule label. | Do not sign investor or financing agreements. |
| Ownership/equity | Record the stop-rule label. | Do not claim ownership or equity allocation closure. |
| Accounting readiness | Record the stop-rule label. | Do not claim accounting readiness. |
| Insurance readiness | Record the stop-rule label. | Do not claim insurance readiness. |
| Legal clearance | Record the stop-rule label. | Do not claim legal clearance. |
| Money movement | Record the stop-rule label. | Do not move money. |
| Customer access | Record the stop-rule label. | Do not open customer access. |
| Publication/deployment | Record the stop-rule label. | Do not publish externally or deploy. |
| Operator reassessment | Record the stop-rule label. | Do not promote formation readiness without evidence. |

## Operator Procedure

1. Treat this boundary as a deferral packet, not as formation readiness.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not store entity names, reserved names, legal-entity identifiers, tax
   identifiers, registered-agent records, addresses, bank values, processor
   values, payroll values, contracts, investor records, ownership allocations,
   URLs, emails, private paths, timestamps, hashes, secrets, or private key
   material in this witness.
4. Stop if the next step requires entity registration, name reservation,
   tax/accounting setup, banking, payment processing, payroll, contracts,
   investor agreements, ownership/equity decisions, insurance setup, legal
   clearance, money movement, customer access, external publication, or
   deployment.
5. Keep the deferral in `AwaitingEvidence` until qualified-review scope,
   permitted storage rules, formation evidence handling, and operator
   reassessment each pass their own future witness checks.

## Validation

Run:

```powershell
python scripts/validate_foundation_company_formation_deferral_boundary.py
```

The validator checks that the company-formation deferral witness:

1. keeps every company-formation deferral surface in `AwaitingEvidence`;
2. keeps formation, registration, names, identifiers, tax records,
   agent/address records, bank accounts, processor accounts, payroll,
   contracts, investor agreements, ownership/equity allocation, accounting,
   insurance, legal clearance, money, customer access, publication, and
   deployment blocked;
3. allows only public-safe deferral labels and blocked-gate notes;
4. rejects URLs, emails, IP-looking values, timestamps, private paths, secret
   material, hash-like values, currency amounts, and assignment shapes for
   company-formation facts; and
5. rejects promotion phrases that imply formation, registration, tax,
   banking, payment, payroll, contracts, investment, ownership/equity,
   accounting, insurance, legal clearance, customer-access, publication, or
   deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Draft legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Keep legal review deferred | [Foundation Legal Review Deferral Boundary](FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md) |
| Keep funding/team obligations closed | [Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md) |
| Keep payments closed | [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: company formation blocked, entity registration blocked, entity-name reservation blocked, legal-entity identifiers blocked, tax identifiers blocked, registered-agent records blocked, business-address records blocked, business bank accounts blocked, payment processor accounts blocked, payroll setup blocked, contractor agreements blocked, investor agreements blocked, ownership/equity allocation claims blocked, accounting readiness blocked, insurance readiness blocked, legal clearance blocked, money movement blocked, customer access blocked, external publication blocked, deployment blocked
  Open issues: all company-formation deferral surfaces remain AwaitingEvidence
  Next action: validate this company-formation deferral before any future formation, tax, banking, payment, contractor, investor, customer, publication, or deployment work
