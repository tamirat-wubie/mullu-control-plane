<!--
Purpose: define the atomic prerequisite ladder for solo-founder Foundation Mode.
Governance scope: local setup, evidence readiness, claim boundaries, legal/business separation, deployment restraint, and reversible next actions.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md, docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md, docs/FOUNDATION_LOCAL_PROOF_THREAD.md, docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md, docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md, docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/START_HERE.md, docs/CURRENT_READINESS_SNAPSHOT.md, DEPLOYMENT_STATUS.md, AGENTS.md.
Invariants: no public deployment claim, no customer access claim, no paid infrastructure requirement, no legal conclusion, no irreversible external action by default.
-->

# Foundation Prerequisites

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** this is the checklist for preparing the foundation before
> launch. It does not mean you are opening access, deploying a runtime, forming
> a company, filing a patent, spending money, or taking customers. It means each
> prerequisite is made visible, small, reversible, and evidence-bound.

This page is the practical companion to [Foundation Mode](FOUNDATION_MODE.md).
Use it when the next step feels too broad. Pick one row, close one small
evidence item, then stop and re-evaluate.

Rule: No customer access or deployment claim.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| `NotStarted` | No evidence has been collected yet. |
| `InProgress` | Local preparation exists, but evidence is incomplete. |
| `EvidenceLocal` | Local file, test, receipt, or note exists in the workspace. |
| `AwaitingEvidence` | A hard dependency needs sensing, proof, qualified review, or an external witness. |
| `DelayedByDesign` | The action is intentionally later because it creates cost, exposure, or obligation. |
| `Blocked` | A hard constraint prevents progress until a specific prerequisite closes. |

## Atomic Prerequisite Ledger

| Layer | Current posture | Prepare now | Do not do yet | Evidence to keep |
| --- | --- | --- | --- | --- |
| Operator readiness | Solo operator | Keep steps small, written, and reversible. | Do not create team/process complexity. | Dated notes, commits, local receipts. |
| Source control | Local repository work | Use [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) to keep clean diffs, meaningful commits, branch boundaries, and no-secret checks explicit. | Do not publish sensitive internals. | Git status, commit messages, PR summaries. |
| Local workstation | Local-first setup | Verify Python, Node, Rust, tests, and repeatable local commands. | Do not depend on paid cloud to prove basics. | Test logs and preflight receipts. |
| Documentation | Foundation docs active | Keep plain-English status, glossary, and next action clear. | Do not describe the product as customer-ready. | Updated docs and validator output. |
| Claim boundary | Foundation-stage claims | Separate repository proof, public copy, runtime proof, and legal claims. | Do not imply production health or endpoint readiness. | Readiness snapshots and public naming checks. |
| Security basics | Public-safe only | Keep secrets out of files and fixtures; classify external calls. | Do not wire live credentials into public artifacts. | Secret-scan results and policy receipts. |
| Secrets/credentials | Draft categories only | Use [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) to draft credential categories, environment-variable names, provider-access questions, key questions, and rotation questions locally. | Do not store real secrets, activate credentials, bind provider accounts, enable external calls, or commit environment files. | Secrets/credentials witness and local draft checklist. |
| Cost/budget | No spend by default | Use [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) to draft cost categories, budget questions, billing questions, payment-method questions, subscription questions, and purchase controls locally. | Do not spend, enable billing, bind payment methods, create subscriptions, approve purchases, pay invoices, or activate paid infrastructure. | Cost/budget witness and local draft checklist. |
| Runtime/environment | Draft checks only | Use [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) to draft local command, toolchain, dependency, database, container, endpoint, migration, and rollback questions. | Do not claim runtime readiness, start services, activate databases, open endpoints, connect cloud runtimes, run migrations, or deploy. | Runtime/environment witness and local draft checklist. |
| Backup/export | Draft plan only | Use [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) to draft backup inventory, export scope, archive, restore-drill, redaction, retention, deletion, and handoff questions locally. | Do not run backups, activate cloud sync, export files, publish archives, delete data, record private paths, move secrets, move personal data, claim restore readiness, or deploy. | Backup/export witness and local draft checklist. |
| Account recovery | Needs private owner evidence | Use [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) to create a private recovery inventory outside public docs. | Do not store recovery codes or account secrets in this repo. | Private inventory reference, not secret content. |
| Domain and email | Existing public identity, incomplete readiness evidence | Use [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) to record DNS/email posture in public-safe witness form. | Do not expose provider account IDs or private DNS targets. | Public-safe DNS/email witness notes. |
| Legal/business | Pre-clearance | Use [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) to separate trademark, company, tax, patent, terms, compliance, and payment questions. | Do not claim legal clearance, patent protection, or company readiness. | Questions list and qualified-review TODOs. |
| Product scope | Product direction | Use [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) to select one local learning lane while preserving the broader platform direction. | Do not market broad platform promises or treat the lane as a pilot. | Product-scope witness and one proof-thread goal. |
| Support readiness | Support direction | Use [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) to draft support, triage, incident, rollback, and closure surfaces locally. | Do not open support, promise response time, claim incident readiness, or start onboarding. | Support-readiness witness and local draft checklist. |
| Intake/onboarding | Future intake direction | Use [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) to draft intake fields, consent questions, onboarding steps, and retention questions locally. | Do not publish forms, open waitlists, accept pilot signups, collect personal data, import CRM records, start outreach, or onboard customers. | Intake/onboarding witness and local draft checklist. |
| Privacy/data | Data handling direction | Use [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) to draft privacy, consent, retention, deletion, processor, tracking, and minimization questions locally. | Do not collect or store personal data, publish privacy notices, capture consent, enable tracking, activate processors, or claim legal clearance. | Privacy/data witness and local draft checklist. |
| Local proof thread | Descriptor, validator, and local runner prepared | Use [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md) to keep the first workflow local, approval-gated, receipt-bound, and rollback-named. | Do not connect real payments, users, or public endpoints. | Workflow descriptor, validator output, local result, receipt, audit, rollback note. |
| Website posture | Public static boundary | Keep website copy in Foundation Mode. | Do not open pilot, beta, waitlist, or access wording. | Website validation and claim-gate output. |
| Deployment | Delayed by design | Keep deployment prerequisites classified. | Do not deploy runtime or claim public health by default. | `DEPLOYMENT_STATUS.md` and deployment witness plan. |
| Pilot | Delayed by design | Define what a future narrow pilot would require. | Do not invite users or accept intake. | Pilot boundary notes, support plan, rollback plan. |

## Recommended Order

1. Keep the current Foundation Mode boundary intact.
2. Close local workstation repeatability: setup commands, tests, and preflight.
3. Close source-control hygiene: commit boundary, branch boundary, and no secret drift using [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md).
4. Prepare secrets/credentials notes using [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md).
5. Prepare cost/budget notes using [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md).
6. Prepare runtime/environment notes using [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md).
7. Prepare backup/export notes using [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md).
8. Close one local proof thread with a receipt and rollback note.
9. Update the plain-English docs so a non-technical reader sees the exact state.
10. Prepare private recovery inventory outside the repository using [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md).
11. Prepare domain/email public-safe witness notes using [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md).
12. Prepare product-scope learning lane notes using [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md).
13. Prepare support-readiness notes using [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md).
14. Prepare intake/onboarding notes using [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md).
15. Prepare privacy/data notes using [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md).
16. Prepare legal/business questions without making legal claims using [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md).
17. Reassess whether deployment prerequisites should even start.

## Narrow Local Proof Thread Definition

A narrow local proof thread is one tiny workflow that proves the control shape.
The canonical first thread is [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md):

```text
local input
  -> classify intent
  -> check policy and authority
  -> require local approval if needed
  -> perform a harmless local action
  -> write a receipt
  -> verify result
  -> record rollback or recovery path
```

It is intentionally narrow because the purpose is proof of structure, not proof
of market demand, public hosting, legal readiness, or business viability.

## External Prerequisites Are Evidence Problems

External infrastructure is not just "servers." In this project, it means every
outside dependency that can create cost, exposure, lockout, legal obligation, or
public trust:

| External area | Why it matters | Foundation Mode treatment |
| --- | --- | --- |
| Domains and DNS | Controls public identity and routing. | Record current state; avoid risky mutation until recovery is ready. |
| Email and workspace | Controls identity, support, and account recovery. | Keep mailboxes visible; protect admin and recovery paths privately. |
| Hosting and databases | Creates runtime exposure and recurring cost. | Delay until local proof and rollback are strong. |
| Secrets and credentials | Can create account compromise or cost. | Use [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md); never store real secrets in public docs or fixtures. |
| Cost and budget | Can create recurring spend or irreversible vendor obligations. | Use [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md); never bind payment methods or approve purchases in Foundation Mode. |
| Runtime and environment | Can create false readiness, state changes, or endpoint exposure. | Use [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md); never claim runtime readiness or deploy from draft checks. |
| Backup and export | Can expose private paths, secrets, personal records, or incomplete restore claims. | Use [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md); never run backups, cloud sync, exports, public archives, deletion, or restore claims from draft planning. |
| Legal/business filings | Create obligations and public claims. | Prepare questions; get qualified review later. |
| Payment providers | Create money movement and compliance risk. | Simulate locally; do not process real payments in Foundation Mode. |
| Customer access | Creates support, safety, and trust duties. | Keep closed until scope, support, terms, and rollback exist. |

## Assistant Operating Rule

When a future request says "continue," use this order unless the user names a
different target:

1. preserve Foundation Mode;
2. choose the smallest prerequisite that improves local proof or clarity;
3. avoid irreversible external action;
4. validate with local tests or governance preflight;
5. report what changed, what is still uncommitted, and what remains
   `AwaitingEvidence`.

---

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| Understand why this mode exists | [Foundation Mode](FOUNDATION_MODE.md) |
| Prepare source-control commit boundary | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Prepare secrets/credentials without live credentials | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Prepare cost/budget without spending | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare runtime/environment without deployment | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) |
| Prepare backup/export without moving data | [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) |
| Prepare owner-only recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Prepare domain/email public-safe witness | [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) |
| Prepare product scope without restricting the platform | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) |
| Prepare support readiness without opening support | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare intake/onboarding without opening access | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare privacy/data without handling people data | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| See current public claim truth | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |
| Start from the front door | [Start Here](START_HERE.md) |
| Check runtime publication truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |
| Understand terms | [Glossary](GLOSSARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: local proof first, reversible steps, no deployment claim, no customer access claim, no legal conclusion
  Open issues: secrets/credentials evidence, cost/budget evidence, runtime/environment evidence, backup/export evidence, private recovery evidence, support evidence, intake/onboarding evidence, privacy/data evidence, legal review, runtime witness, and pilot support plan remain AwaitingEvidence
  Next action: pick one ledger row and close one local evidence item
