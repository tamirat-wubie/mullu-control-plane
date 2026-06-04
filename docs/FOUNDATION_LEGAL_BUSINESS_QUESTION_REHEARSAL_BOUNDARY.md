<!--
Purpose: define the Foundation Mode legal/business question rehearsal boundary for public-safe local preparation without legal conclusions, filings, formation, paid launch, customer access, money movement, external publication, or deployment.
Governance scope: local legal/business question rehearsal, qualified-review gating, claim blocking, private-material exclusion, customer-access blocking, paid-launch blocking, money-movement blocking, external-publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, examples/foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_legal_business_question_rehearsal_boundary.py.
Invariants: no legal conclusion, no legal clearance claim, no qualified review completion claim, no company formation claim, no company readiness claim, no patent filing or protection claim, no trademark clearance claim, no tax readiness claim, no terms/privacy readiness claim, no compliance clearance claim, no contractor/team commitment, no paid launch, no payment or money movement, no customer access, no external publication, no secret or private reviewer material, and no deployment claim.
-->

# Foundation Legal Business Question Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** legal/business question rehearsal means organizing public-safe
> question categories for a future qualified reviewer. It does not answer the
> questions, complete review, create a company, file anything, claim clearance,
> handle secrets, open customer access, accept payment, move money, publish
> externally, or deploy anything.

Witness packet: [`../examples/foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json)

Rule: Legal/business question rehearsal is a local paper exercise, not a legal
or business approval path.

No legal conclusion, legal clearance, qualified review completion, company
formation, company readiness, patent filing, patent protection, trademark
clearance, tax readiness, terms/privacy readiness, compliance clearance,
contractor/team commitment, paid launch, payment processing, money movement,
customer access, external publication, secret/private reviewer material, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

The broader legal/business boundary says review is required. A solo operator
still needs a safe way to sort the questions before any real reviewer,
formation step, filing, contract, tax step, payment step, customer access, or
deployment work exists.

This is preparation only:

1. Draft local public-safe question categories.
2. Keep every category in `AwaitingEvidence`.
3. Keep evidence references as `manual_preparation_pending`.
4. Do not store reviewer names, account IDs, filing IDs, tax IDs, payment IDs,
   customer IDs, URLs, emails, private paths, secrets, or private key material.
5. Do not claim legal readiness, business readiness, customer readiness, paid
   launch readiness, or deployment readiness from this rehearsal.

## Current State

```text
legal_business_question_rehearsal_boundary_state=AwaitingEvidence
question_rehearsal_executed=false
legal_conclusion_claimed=false
legal_clearance_claimed=false
qualified_review_completed=false
company_formation_allowed=false
company_readiness_claimed=false
patent_filing_allowed=false
patent_protection_claimed=false
trademark_clearance_claimed=false
tax_readiness_claimed=false
terms_privacy_readiness_claimed=false
compliance_clearance_claimed=false
contractor_team_commitment_allowed=false
paid_launch_allowed=false
payment_processing_allowed=false
money_movement_allowed=false
customer_access_allowed=false
external_publication_allowed=false
secret_or_private_reviewer_material_allowed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Ownership/invention questions | Draft public-safe authorship and invention-history questions. | Do not claim ownership closure or invention authorship finality. |
| Naming/trademark questions | Draft name-clearance questions. | Do not claim trademark clearance or final brand ownership. |
| Formation timing questions | Draft when formation might need review. | Do not form or claim a company entity. |
| Tax/accounting questions | Draft recordkeeping and tax questions. | Do not claim tax or bookkeeping readiness. |
| Terms/privacy questions | Draft future terms and notice questions. | Do not claim terms/privacy readiness or open customer access. |
| Patent/invention questions | Draft invention-boundary questions. | Do not file, publish, or claim patent protection. |
| Compliance/data questions | Draft data and regulated-use questions. | Do not claim compliance clearance. |
| Finance/payment questions | Draft payment-provider and ledger questions. | Do not process payment, accept paid access, or move money. |
| Contractor/team questions | Draft contribution and access-control questions. | Do not invite contributors, hire, engage contractors, or promise equity. |
| Support/liability questions | Draft future support-duty questions. | Do not open support commitments, customer channels, or liability claims. |
| Qualified-review handoff | Draft what a future reviewer would need. | Do not store private reviewer material or claim review completion. |

## Operator Procedure

1. Keep all examples fictional, local, and public-safe.
2. Draft question categories only; do not answer them as conclusions.
3. Exclude URLs, emails, private filesystem paths, account values, filing
   values, tax values, payment values, customer values, reviewer values,
   secrets, and private key material.
4. Stop if work requires legal judgment, company formation, filing, trademark
   or patent action, tax action, terms/privacy approval, customer access,
   payment, money movement, public publication, external outreach, or
   deployment.
5. Use the result only as a future review checklist.

## Validation

Run:

```powershell
python scripts/validate_foundation_legal_business_question_rehearsal_boundary.py
```

The validator checks that the legal/business question rehearsal witness:

1. keeps legal conclusions, legal clearance, qualified review completion,
   formation, filings, trademark, tax, terms/privacy, compliance, team,
   payment, money movement, customer access, publication, secret/private
   reviewer material, and deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. rejects URL, email, private path, account, reviewer, filing, tax, payment,
   customer, secret, private-key, and deployment-shaped values; and
5. rejects promotion phrases that imply legal/business readiness, review
   completion, filings, company formation, customer access, paid launch, money
   movement, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the broader legal/business boundary | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare privacy/data without handling people data | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Keep customer access closed | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: legal conclusion blocked, legal clearance blocked, qualified review completion blocked, company formation blocked, company readiness blocked, patent filing blocked, patent protection blocked, trademark clearance blocked, tax readiness blocked, terms/privacy readiness blocked, compliance clearance blocked, contractor/team commitment blocked, paid launch blocked, payment processing blocked, money movement blocked, customer access blocked, external publication blocked, secret/private reviewer material blocked, deployment blocked
  Open issues: ownership/invention evidence, naming/trademark evidence, formation-timing evidence, tax/accounting evidence, terms/privacy evidence, patent/invention evidence, compliance/data evidence, finance/payment evidence, contractor/team evidence, support/liability evidence, and qualified-review handoff remain AwaitingEvidence
  Next action: run the legal/business question rehearsal validator before relying on question organization as evidence
