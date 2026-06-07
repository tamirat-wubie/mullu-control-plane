<!--
Purpose: define the Foundation Mode boundary for deferring patent filing, patent-protection claims, invention finality, disclosure approval, public research publication, secret/trade-secret protection claims, customer access, money movement, company formation, legal clearance, and deployment.
Governance scope: local patent/disclosure deferral, invention-boundary blocking, authorship/ownership finality blocking, prior-art/novelty/patentability blocking, publication blocking, private-value exclusion, legal/company blocking, payment blocking, customer-access blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md, examples/foundation_patent_disclosure_deferral_witness.awaiting_evidence.json, scripts/validate_foundation_patent_disclosure_deferral_boundary.py.
Invariants: no patent filing, no patent-protection claim, no invention-boundary finality, no invention-authorship finality, no ownership finality, no prior-art conclusion, no novelty claim, no patentability claim, no disclosure approval, no public research publication, no external publication, no secret/trade-secret protection claim, no legal clearance, no company formation, no paid launch, no money movement, no customer access, and no deployment claim.
-->

# Foundation Patent Disclosure Deferral Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** patent/disclosure deferral means recording that patent,
> invention, authorship, ownership, prior-art, novelty, patentability,
> disclosure, publication, secrecy, legal, company, customer, payment, and
> deployment gates are not ready. It does not file anything, protect anything,
> approve disclosure, publish research, move money, invite customers, form a
> company, clear legal risk, or deploy.

Witness packet: [`../examples/foundation_patent_disclosure_deferral_witness.awaiting_evidence.json`](../examples/foundation_patent_disclosure_deferral_witness.awaiting_evidence.json)

Rule: Patent/disclosure deferral is a local stop-rule packet for future
qualified review. It is not legal advice, not patent filing, not patent
protection, not invention finality, not disclosure approval, not publication
approval, not secrecy protection, not customer authority, and not deployment
readiness.

No patent filing, patent protection claim, invention-boundary finality,
invention-authorship finality, ownership finality, prior-art conclusion,
novelty claim, patentability claim, disclosure approval, public research
publication, external publication, secret/trade-secret protection claim, legal
clearance, company formation, paid launch, money movement, customer access, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode already keeps legal, company, and research claims blocked.
This boundary makes the patent/disclosure stop rule explicit for a solo
operator who is still pre-review, pre-filing, pre-disclosure, pre-publication,
pre-company, pre-customer, and pre-deployment.

Use it when the question is:

1. Which patent/disclosure facts must stay out of Git and public docs?
2. Which invention, authorship, ownership, novelty, or patentability gates are
   only labels today?
3. Which disclosure or publication actions are blocked before review?
4. Which secrecy or protection claims are unsafe without outside evidence?
5. Which reassessment step must happen before any disclosure work begins?

## Current State

```text
patent_disclosure_deferral_state=AwaitingEvidence
patent_filing_allowed=false
patent_protection_claimed=false
invention_boundary_final_claimed=false
invention_authorship_final_claimed=false
ownership_claim_finalized=false
prior_art_conclusion_recorded=false
novelty_claimed=false
patentability_claimed=false
disclosure_approval_claimed=false
public_research_publication_allowed=false
external_publication_allowed=false
secret_or_trade_secret_protection_claimed=false
legal_clearance_claimed=false
company_formation_claimed=false
paid_launch_allowed=false
money_movement_allowed=false
customer_access_allowed=false
deployment_allowed=false
```

## Public-Safe Deferral Labels

These labels are stop-rule gates only. They are not patent filings, application
numbers, invention disclosures, inventor records, ownership records, prior-art
records, novelty opinions, patentability opinions, publication receipts,
secrecy claims, reviewer records, timestamps, hashes, private paths, account
identifiers, URLs, emails, or deployment receipts.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `patent_filing_gate` | Future filing-authority gate. | Do not file or claim a patent filing. |
| `patent_protection_gate` | Future protection-evidence gate. | Do not claim patent protection. |
| `invention_boundary_gate` | Future invention-scope gate. | Do not claim invention-boundary finality. |
| `invention_authorship_gate` | Future authorship-evidence gate. | Do not claim invention authorship finality. |
| `ownership_claim_gate` | Future ownership-evidence gate. | Do not claim ownership finality. |
| `prior_art_review_gate` | Future prior-art review gate. | Do not claim prior-art conclusions. |
| `novelty_claim_gate` | Future novelty-evidence gate. | Do not claim novelty. |
| `patentability_claim_gate` | Future patentability-evidence gate. | Do not claim patentability. |
| `disclosure_approval_gate` | Future disclosure-approval gate. | Do not approve disclosure. |
| `public_research_publication_gate` | Future research-publication gate. | Do not publish research externally. |
| `external_publication_gate` | Future external-publication gate. | Do not approve external publication. |
| `secret_protection_claim_gate` | Future secrecy/protection gate. | Do not claim secret or trade-secret protection. |
| `legal_clearance_gate` | Future legal-clearance gate. | Do not claim legal clearance. |
| `company_formation_gate` | Future company-formation gate. | Do not claim company formation. |
| `paid_launch_gate` | Future paid-launch gate. | Do not open paid launch. |
| `money_movement_gate` | Future money-movement gate. | Do not move money. |
| `customer_access_gate` | Future customer-access gate. | Do not open customer access. |
| `deployment_gate` | Future deployment gate. | Do not deploy. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve patent/disclosure promotion. |

## Deferral Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Patent filing | Record the stop-rule label. | Do not file or claim a patent filing. |
| Patent protection | Record the stop-rule label. | Do not claim patent protection. |
| Invention boundary | Record the stop-rule label. | Do not claim invention-boundary finality. |
| Invention authorship | Record the stop-rule label. | Do not claim authorship finality. |
| Ownership | Record the stop-rule label. | Do not claim ownership finality. |
| Prior-art review | Record the stop-rule label. | Do not claim prior-art conclusions. |
| Novelty | Record the stop-rule label. | Do not claim novelty. |
| Patentability | Record the stop-rule label. | Do not claim patentability. |
| Disclosure approval | Record the stop-rule label. | Do not approve disclosure. |
| Public research publication | Record the stop-rule label. | Do not publish research externally. |
| External publication | Record the stop-rule label. | Do not approve external publication. |
| Secret protection | Record the stop-rule label. | Do not claim secret or trade-secret protection. |
| Legal clearance | Record the stop-rule label. | Do not claim legal clearance. |
| Company formation | Record the stop-rule label. | Do not claim company formation. |
| Paid launch | Record the stop-rule label. | Do not open paid launch. |
| Money movement | Record the stop-rule label. | Do not move money. |
| Customer access | Record the stop-rule label. | Do not open customer access. |
| Deployment | Record the stop-rule label. | Do not deploy. |
| Operator reassessment | Record the stop-rule label. | Do not promote patent/disclosure readiness without evidence. |

## Operator Procedure

1. Treat this boundary as a deferral packet, not as patent, disclosure, or
   publication readiness.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not store patent application values, filing values, invention disclosure
   records, inventor identities, ownership records, prior-art conclusions,
   novelty opinions, patentability opinions, reviewer identities, secrecy
   claims, URLs, emails, private paths, timestamps, hashes, secrets, or private
   key material in this witness.
4. Stop if the next step requires patent filing, public disclosure, external
   publication, legal review, company formation, customer access, money
   movement, paid launch, or deployment.
5. Keep the deferral in `AwaitingEvidence` until qualified-review scope,
   permitted storage rules, disclosure handling, publication handling, and
   operator reassessment each pass their own future witness checks.

## Validation

Run:

```powershell
python scripts/validate_foundation_patent_disclosure_deferral_boundary.py
```

The validator checks that the patent/disclosure deferral witness:

1. keeps every patent/disclosure deferral surface in `AwaitingEvidence`;
2. keeps patent filing, patent protection, invention finality, authorship
   finality, ownership finality, prior-art conclusions, novelty,
   patentability, disclosure approval, publication, secrecy/protection claims,
   legal clearance, company formation, paid launch, money movement, customer
   access, and deployment blocked;
3. allows only public-safe deferral labels and blocked-gate notes;
4. rejects URLs, emails, IP-looking values, timestamps, private paths, secret
   material, hash-like values, and assignment shapes for patent/disclosure
   facts; and
5. rejects promotion phrases that imply filing, protection, invention finality,
   authorship finality, ownership finality, prior-art clearance, novelty,
   patentability, disclosure approval, publication, secrecy protection, legal
   clearance, company formation, paid launch, money movement, customer access,
   or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Organize research notes safely | [Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md) |
| Draft legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Keep legal review deferred | [Foundation Legal Review Deferral Boundary](FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md) |
| Keep company formation deferred | [Foundation Company Formation Deferral Boundary](FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: patent filing blocked, patent protection blocked, invention-boundary finality blocked, invention-authorship finality blocked, ownership finality blocked, prior-art conclusions blocked, novelty claims blocked, patentability claims blocked, disclosure approval blocked, public research publication blocked, external publication blocked, secret/trade-secret protection claims blocked, legal clearance blocked, company formation blocked, paid launch blocked, money movement blocked, customer access blocked, deployment blocked
  Open issues: all patent/disclosure deferral surfaces remain AwaitingEvidence
  Next action: validate this patent/disclosure deferral before any future filing, disclosure, publication, legal, company, customer, payment, or deployment work
