<!--
Purpose: define the public-safe legal and business question boundary for Foundation Mode.
Governance scope: legal/business pre-clearance, question inventory, qualified-review gating, claim blocking, and no irreversible external action.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_legal_business_questions.awaiting_review.json, scripts/validate_foundation_legal_business_boundary.py.
Invariants: no legal clearance claim, no company readiness claim, no patent protection claim, no trademark clearance claim, no tax readiness claim, no customer terms readiness claim, no paid launch claim, no money movement claim.
-->

# Foundation Legal Business Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** this boundary turns legal and business uncertainty into a
> public-safe question packet. It does not form a company, file a patent, clear
> a trademark, approve taxes, open customer terms, authorize paid launch, or
> move money.

Question packet: [`../examples/foundation_legal_business_questions.awaiting_review.json`](../examples/foundation_legal_business_questions.awaiting_review.json)

Rule: Legal and business readiness stays `AwaitingEvidence` until qualified
review or a later signed witness promotes a specific item.

No legal clearance, company readiness, patent protection, trademark clearance,
tax readiness, customer terms readiness, paid launch, or money movement claim is
permitted in Foundation Mode.

## What This Boundary Solves

The project has many legal and business surfaces, but a solo founder can prepare
them without taking external action. The safe work is to write questions,
separate topics, preserve invention history, and keep claims blocked until
qualified review.

This boundary keeps that work small:

1. The repository records questions and blocked claims.
2. The repository does not record legal conclusions.
3. The packet remains `AwaitingEvidence`.
4. External filing, spending, customer intake, and legal promotion remain
   blocked by default.

## Question Areas

| Area | Prepare now | Do not claim |
| --- | --- | --- |
| Ownership and invention record | Dated notes, authorship records, contribution boundary. | Ownership dispute resolved. |
| Public name and trademark | Candidate names, usage list, review questions. | Trademark clearance. |
| Company formation | Formation questions and timing constraints. | Company readiness. |
| Tax and accounting | Questions for income, expenses, bookkeeping, and filing timing. | Tax readiness. |
| Terms and privacy | Draft question list for future customer-facing terms. | Customer terms readiness. |
| Patent and invention boundary | Invention notes and claim questions for qualified review. | Patent protection. |
| Data and compliance | Data categories and compliance questions. | Compliance clearance. |
| Finance and payments | Payment-provider questions and money-movement blockers. | Money movement allowed. |
| Contractors and team | Ownership, confidentiality, and contribution questions. | Team process readiness. |
| Support and liability | Support duty, incident duty, and rollback questions. | Customer support readiness. |

## Current State

```text
legal_business_boundary_state=AwaitingEvidence
qualified_review_required=true
legal_clearance_claimed=false
company_ready_claimed=false
patent_protection_claimed=false
paid_launch_allowed=false
money_movement_allowed=false
```

## Operator Procedure

1. Use the question packet as a checklist.
2. Add only public-safe question refinements.
3. Keep private reviewer communications outside Git unless they are explicitly
   safe to summarize.
4. Promote one topic only when qualified review or a signed witness exists.
5. Do not combine legal, company, patent, tax, terms, payment, or customer
   readiness into one broad claim.

## Validation

Run:

```powershell
python scripts/validate_foundation_legal_business_boundary.py
```

The validator checks that the question packet:

1. keeps every domain in `AwaitingEvidence`;
2. keeps every readiness claim false;
3. keeps paid launch and money movement blocked;
4. rejects readiness-promotion drift; and
5. preserves the required question areas.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: question-only boundary, qualified review required, no legal clearance claim, no company readiness claim, no patent protection claim, no paid launch claim, no money movement claim
  Open issues: qualified legal/business/tax review remains AwaitingEvidence
  Next action: run the legal/business boundary validator, then refine one question area at a time
