<!--
Purpose: define the repo-level Foundation Mode company-boundary kernel for Mullu Control Plane before legal, financial, customer, infrastructure, deployment, IP, or compliance obligations are promoted.
Governance scope: Foundation company-boundary governance, repository claim control, ownership and IP provenance, secrets and recovery restraint, asset-control readiness, continuity planning, customer/payment/deployment/legal/patent deferral, and external-obligation prevention.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_CLAIM_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md, docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md, docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md, docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, examples/foundation_company_boundary_kernel_witness.awaiting_evidence.json, scripts/validate_foundation_company_boundary_kernel.py.
Invariants: no company-formation proof, no legal conclusion, no trademark claim, no patent claim, no compliance certification, no customer-readiness claim, no deployment-readiness claim, no payment activation, no money movement, no real secret storage, no external obligation, and no production claim.
-->

# Mullu Control Plane Company Boundary Kernel

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** this kernel defines what must be true before the repository
> can promote legal, financial, customer, infrastructure, deployment, IP, or
> compliance obligations. It is a Foundation Mode control document, not a proof
> that any of those obligations already exist.

Witness packet: [`../examples/foundation_company_boundary_kernel_witness.awaiting_evidence.json`](../examples/foundation_company_boundary_kernel_witness.awaiting_evidence.json)

Machine-readable ledger: [`../governance/company_boundary_kernel.yaml`](../governance/company_boundary_kernel.yaml)

Rule: This document does not authorize company formation, legal claims, customer
access, deployment, payment activation, patent filing, trademark claim,
compliance certification, money movement, public launch, or external
obligation. It defines the evidence boundary required before any of those
actions can be promoted.

## Current Status

```text
company_boundary_kernel_state=AwaitingEvidence
foundation_mode_required=true
company_formation_authorized=false
legal_claim_authorized=false
customer_access_authorized=false
deployment_authorized=false
payment_activation_authorized=false
patent_filing_authorized=false
trademark_claim_authorized=false
compliance_certification_authorized=false
external_obligation_authorized=false
money_movement_allowed=false
```

Current wording may use "intended Mullusi company boundary" or
"Mullusi-controlled boundary" while formation evidence remains
`AwaitingEvidence`. Do not treat repository ownership notices, proprietary
license terms, or local governance docs as company-formation evidence.

## Boundary Kernel

| Kernel surface | Prepare now | Blocked now |
| --- | --- | --- |
| Entity status | Track formation questions and evidence classes. | Do not claim company formation, legal-entity registration, entity name reservation, or tax identifier readiness. |
| Ownership and IP status | Record provenance classes for repository artifacts. | Do not claim final IP clearance, patent protection, trademark ownership, contributor assignment, or contractor assignment without evidence. |
| Repository and infrastructure control | Inventory control surfaces by class. | Do not record live account identifiers, mutate DNS, provision cloud, bind secrets, activate billing, or claim infrastructure readiness. |
| Secrets and recovery control | Keep recovery categories and private-inventory stop rules visible. | Do not store plaintext secrets, private keys, tokens, seed phrases, recovery codes, or private inventory values in Git. |
| Money and tax separation | Keep spending, billing, and tax gates explicit. | Do not bind payment methods, activate payment providers, charge customers, pay invoices, record tax identifiers, or move money. |
| Customer contract readiness | Draft future terms, privacy, support, and rollback questions. | Do not open pilots, waitlists, beta access, intake, customer accounts, support obligations, public API access, or production access. |
| Privacy and data readiness | Record data-classification and minimization questions. | Do not collect customer or personal data, activate processors, publish privacy-readiness claims, or claim retention/deletion readiness. |
| Insurance and risk review | Track future insurance and risk-review questions. | Do not claim insurance readiness, liability coverage, compliance certification, or risk approval. |
| Continuity plan | Identify role categories and transfer/shutdown questions. | Do not store secrets, private contact details, live account IDs, or emergency credentials in the repository. |
| Shutdown or transfer path | Draft public-safe exit and transfer criteria. | Do not authorize transfer, sale, shutdown, account handoff, legal action, or external communication from this document. |

## Repo Claim Boundary

No repository file may imply any of these states unless evidence exists and a
later status witness promotes the specific claim:

1. Company fully formed.
2. Trademark ownership or clearance secured.
3. Patent filed, protected, or cleared for disclosure.
4. Legal review complete.
5. Compliance certification complete.
6. Customer readiness or pilot readiness.
7. Deployment readiness or production health.
8. Payment-provider readiness, tax readiness, or money movement approval.
9. Insurance readiness or liability coverage.
10. Continuity transfer, emergency authority, or shutdown approval.

## IP and Provenance Boundary

Every committed artifact should be classifiable before it is treated as core
Mullusi-controlled IP:

| Provenance class | Repository treatment |
| --- | --- |
| `founder_created` | Keep authorship and local evidence visible. |
| `symbolic_intelligence_assisted` | Review before treating as core IP. |
| `generated_artifact` | Keep generation source, input class, and review status traceable. |
| `third_party_dependency` | Keep dependency source and license class visible. |
| `open_source_dependency` | Keep license obligations visible before distribution. |
| `contractor_contributor_created` | Require written authorization or assignment before acceptance. |
| `externally_derived` | Require source, permission, and transformation evidence before use. |

No contributor work is accepted as core controlled material without one of:

1. signed contributor agreement;
2. explicit written internal Mullusi authorization;
3. contractor IP assignment;
4. documented license compatibility and attribution path.

## Asset and Control Boundary

The kernel covers these future control surfaces:

1. repository owner/admin control;
2. GitHub organization or account admin control;
3. domain registrar and DNS control;
4. workspace/email admin control;
5. cloud account control;
6. API account control;
7. deployment credentials and repository variables;
8. payment-provider accounts;
9. customer-data systems;
10. legal, tax, accounting, and insurance document custody.

In Foundation Mode, these remain draft or rehearsal surfaces unless a named
witness promotes one exact external action. Public-safe docs may identify
classes and gates. They must not record live values.

## Enforcement Rules

| Rule | Enforcement |
| --- | --- |
| R1 | No file may imply company formation unless formation evidence is linked and promoted. |
| R2 | No file may imply trademark or patent protection unless reviewed evidence exists. |
| R3 | No file may imply customer readiness unless customer-access gates are promoted. |
| R4 | No file may imply deployment readiness unless runtime and deployment witnesses pass. |
| R5 | No file may store real secrets or live credential values. |
| R6 | No external service may be activated from the repository without an approval witness. |
| R7 | No contributor work is accepted without IP or licensing provenance. |
| R8 | No payment-provider path is activated without tax, legal, and payment review. |
| R9 | No customer data path is activated without privacy and data classification. |
| R10 | No production claim is allowed without an evidence receipt. |

## Evidence Ledger

Promotion from `Draft` to `Active` requires evidence for the exact surface being
promoted. One promoted surface does not promote the others.

| Evidence class | Required before promotion |
| --- | --- |
| Entity status | Qualified formation evidence and permitted storage rule. |
| Ownership/IP | Authorship, license, assignment, or authorization evidence. |
| Repository/infrastructure control | Public-safe control witness, recovery witness, and no-secret review. |
| Secrets/recovery | Owner-only private inventory outside Git plus public-safe confirmation. |
| Money/tax | Tax, payment, budget, and legal review evidence. |
| Customer contracts | Terms/privacy/support/rollback evidence and approval witness. |
| Privacy/data | Data classification, consent, retention, deletion, and processor evidence. |
| Insurance/risk | Qualified risk review and insurance or liability decision evidence. |
| Continuity | Owner-only continuity packet and public-safe witness. |
| Shutdown/transfer | Qualified legal/business review and explicit operator decision witness. |

## Edge Cases

| Edge case | Repo-safe fix |
| --- | --- |
| Repo says "Mullusi company boundary" while formation remains open. | Use "intended Mullusi company boundary" or "Mullusi-controlled boundary" until formation evidence exists. |
| Symbolic-intelligence-assisted code enters the repo. | Mark provenance, review, and treat as non-final until accepted. |
| Future contributor submits code. | Require authorization, assignment, or license compatibility evidence before acceptance. |
| Deployment files exist before deployment approval. | Mark them as local proof or rehearsal only. Do not imply live readiness. |
| Payment integration appears in code. | Mark it as simulation or dormant integration until the payment gate is promoted. |

## Validation

Run:

```powershell
python scripts/validate_foundation_company_boundary_kernel.py
```

The validator checks that the kernel witness:

1. remains `AwaitingEvidence`;
2. keeps formation, legal, customer, deployment, payment, patent, trademark,
   compliance, external obligation, and money movement blocked;
3. preserves the required boundary surfaces and IP provenance classes;
4. rejects live-value shapes and promotion phrases; and
5. preserves the required documentation anchors.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| Use the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Keep public claims bounded | [Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Keep legal review deferred | [Foundation Legal Review Deferral Boundary](FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md) |
| Keep company formation deferred | [Foundation Company Formation Deferral Boundary](FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md) |
| Keep patent disclosure deferred | [Foundation Patent Disclosure Deferral Boundary](FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md) |
| Keep secrets out of Git | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Keep payment activation blocked | [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md) |
| Keep customer access blocked | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: company formation not authorized, legal claims not authorized, customer access blocked, deployment blocked, payment activation blocked, patent filing blocked, trademark claim blocked, compliance certification blocked, external obligations blocked, money movement blocked, real secret storage blocked
  Open issues: all company-boundary surfaces remain AwaitingEvidence until promoted by specific evidence
  Next action: run the company-boundary kernel validator before any future legal, payment, customer, deployment, patent, trademark, compliance, continuity, or external-obligation promotion
