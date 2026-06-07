<!--
Purpose: define the Foundation Mode boundary for deferring legal review completion, legal conclusions, formation, filing, payment, customer-access, publication, and deployment claims until qualified outside evidence exists.
Governance scope: local legal-review deferral, qualified-review gating, legal-conclusion blocking, formation blocking, filing blocking, tax blocking, terms/privacy blocking, compliance blocking, contractor blocking, payment blocking, customer-access blocking, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md, examples/foundation_legal_review_deferral_witness.awaiting_evidence.json, scripts/validate_foundation_legal_review_deferral_boundary.py.
Invariants: no legal review completion claim, no qualified reviewer identity recording, no legal conclusion recording, no legal clearance claim, no trademark clearance claim, no patent protection claim, no company formation, no tax readiness claim, no terms/privacy approval, no compliance clearance claim, no contractor agreement, no paid launch, no payment processing, no customer access, no personal-data collection, no money movement, no external publication, and no deployment claim.
-->

# Foundation Legal Review Deferral Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** legal-review deferral means recording that legal review is
> not complete and cannot be treated as clearance. It does not name reviewers,
> record conclusions, form a company, file patent or trademark material, approve
> tax/terms/privacy/compliance, engage contractors, open customer access,
> process payment, move money, publish externally, or deploy.

Witness packet: [`../examples/foundation_legal_review_deferral_witness.awaiting_evidence.json`](../examples/foundation_legal_review_deferral_witness.awaiting_evidence.json)

Rule: Legal-review deferral is a local stop-rule packet for future qualified
review. It is not legal advice, not a legal conclusion, not clearance, not
company authority, not filing authority, not payment authority, not customer
authority, and not deployment readiness.

No legal review completion claim, qualified reviewer identity recording, legal
conclusion recording, legal clearance claim, trademark clearance claim, patent
protection claim, company formation, tax readiness claim, terms/privacy
approval, compliance clearance claim, contractor agreement, paid launch,
payment processing, customer access, personal-data collection, money movement,
external publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The legal/business boundary and question rehearsal boundary help organize
questions. This boundary prevents those questions from being mistaken for
review completion, clearance, or permission to take outside-world actions.

Use it when the question is:

1. What must stay blocked before qualified review?
2. Which legal-review facts must stay out of Git and public docs?
3. Which future gates are only labels today?
4. Which claims are unsafe until an outside reviewer or signed witness exists?
5. Which reassessment step must happen before legal/business promotion?

## Current State

```text
legal_review_deferral_state=AwaitingEvidence
legal_review_complete_claimed=false
qualified_reviewer_identity_recorded=false
legal_conclusion_recorded=false
legal_clearance_claimed=false
trademark_clearance_claimed=false
patent_protection_claimed=false
company_formation_allowed=false
tax_readiness_claimed=false
terms_privacy_approved=false
compliance_clearance_claimed=false
contractor_agreement_allowed=false
paid_launch_allowed=false
payment_processing_allowed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Deferral Labels

These labels are stop-rule gates only. They are not reviewer identities, legal
opinions, clearance records, filing records, tax records, payment records,
customer records, timestamps, hashes, private paths, account identifiers, or
deployment receipts.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `qualified_review_scope_gate` | Future review-scope gate. | Do not claim review scope is closed. |
| `reviewer_identity_privacy_gate` | Future reviewer identity privacy gate. | Do not record reviewer identity. |
| `legal_conclusion_gate` | Future legal conclusion gate. | Do not record legal conclusions. |
| `legal_clearance_gate` | Future legal clearance gate. | Do not claim legal clearance. |
| `trademark_clearance_gate` | Future trademark clearance gate. | Do not claim trademark clearance. |
| `patent_protection_gate` | Future patent protection gate. | Do not claim patent protection. |
| `company_formation_gate` | Future formation gate. | Do not form or claim a company entity. |
| `tax_readiness_gate` | Future tax-readiness gate. | Do not claim tax readiness. |
| `terms_privacy_gate` | Future terms/privacy gate. | Do not approve terms or privacy readiness. |
| `compliance_clearance_gate` | Future compliance gate. | Do not claim compliance clearance. |
| `contractor_agreement_gate` | Future contractor agreement gate. | Do not engage contractors. |
| `paid_launch_gate` | Future paid-launch gate. | Do not open paid launch. |
| `payment_processing_gate` | Future payment-processing gate. | Do not process payments. |
| `customer_data_gate` | Future customer/data gate. | Do not open customer access or collect personal data. |
| `publication_deployment_gate` | Future publication/deployment gate. | Do not publish externally or deploy. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve legal/business promotion. |

## Deferral Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Review scope | Record the stop-rule label. | Do not claim qualified-review scope closure. |
| Reviewer identity | Record the stop-rule label. | Do not store reviewer identity or private reviewer material. |
| Legal conclusions | Record the stop-rule label. | Do not record conclusions or advice as repository facts. |
| Legal clearance | Record the stop-rule label. | Do not claim legal clearance. |
| Trademark clearance | Record the stop-rule label. | Do not claim brand or name clearance. |
| Patent protection | Record the stop-rule label. | Do not claim protection, filing, or publication readiness. |
| Company formation | Record the stop-rule label. | Do not form or claim an entity. |
| Tax readiness | Record the stop-rule label. | Do not claim tax or bookkeeping readiness. |
| Terms/privacy | Record the stop-rule label. | Do not approve terms, notices, consent, or tracking. |
| Compliance | Record the stop-rule label. | Do not claim compliance clearance. |
| Contractor agreement | Record the stop-rule label. | Do not hire, contract, or promise equity. |
| Paid launch | Record the stop-rule label. | Do not open paid access or promise commercial readiness. |
| Payment processing | Record the stop-rule label. | Do not activate payment processing or move money. |
| Customer/data | Record the stop-rule label. | Do not open access or collect personal data. |
| Publication/deployment | Record the stop-rule label. | Do not publish externally or deploy. |
| Operator reassessment | Record the stop-rule label. | Do not promote readiness without named evidence. |

## Operator Procedure

1. Treat this boundary as a deferral packet, not as review completion.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not store reviewer names, legal opinions, legal conclusions, account
   values, filing values, tax values, company values, payment values, customer
   values, URLs, emails, private paths, timestamps, hashes, secrets, or private
   key material in this witness.
4. Stop if the next step requires legal judgment, outside-world legal action,
   formation, filing, tax action, terms/privacy approval, compliance approval,
   contractor engagement, payment processing, customer access, personal-data
   collection, money movement, external publication, or deployment.
5. Keep the deferral in `AwaitingEvidence` until qualified-review scope,
   permitted storage rules, reviewer handoff, conclusion handling, and operator
   reassessment each pass their own future witness checks.

## Validation

Run:

```powershell
python scripts/validate_foundation_legal_review_deferral_boundary.py
```

The validator checks that the legal-review deferral witness:

1. keeps every legal-review deferral surface in `AwaitingEvidence`;
2. keeps review completion, reviewer identity recording, legal conclusions,
   legal clearance, trademark clearance, patent protection, formation, tax,
   terms/privacy, compliance, contractors, payment, customer access, personal
   data, money movement, publication, and deployment blocked;
3. allows only public-safe deferral labels and blocked-gate notes;
4. rejects URLs, emails, IP-looking values, timestamps, private paths, secret
   material, hash-like values, and assignment shapes for legal-review facts;
   and
5. rejects promotion phrases that imply legal-review completion, clearance,
   formation, filing, tax, terms/privacy, compliance, contractor, paid-launch,
   payment, customer-access, publication, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Draft legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Rehearse question categories only | [Foundation Legal Business Question Rehearsal Boundary](FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md) |
| Keep customer access closed | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |
| Keep payments closed | [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: legal review completion blocked, reviewer identity recording blocked, legal conclusion recording blocked, legal clearance blocked, trademark clearance blocked, patent protection blocked, company formation blocked, tax readiness blocked, terms/privacy approval blocked, compliance clearance blocked, contractor agreement blocked, paid launch blocked, payment processing blocked, customer access blocked, personal-data collection blocked, money movement blocked, external publication blocked, deployment blocked
  Open issues: all legal-review deferral surfaces remain AwaitingEvidence
  Next action: validate this legal-review deferral before any future legal/business promotion, filing, formation, paid launch, customer access, publication, or deployment work
