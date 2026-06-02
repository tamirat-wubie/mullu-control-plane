<!--
Purpose: define the current solo-founder foundation posture for Mullu Govern and Mullu Control Plane work.
Governance scope: planning, documentation, local proof threads, prerequisite setup, claim boundaries, and public-site wording.
Dependencies: README.md, docs/START_HERE.md, docs/CURRENT_READINESS_SNAPSHOT.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md, docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md, docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md, docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md, docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, DEPLOYMENT_STATUS.md, AGENTS.md.
Invariants: no public deployment claim, no public launch claim, no money movement, no external irreversible action, no legal or patent claim without qualified review.
-->

# Foundation Mode

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, future collaborators, reviewers, and assisting developer agents -->

> **In one box:** Foundation Mode means the project is being prepared carefully
> before deployment, company formation, customer access, or paid infrastructure.
> The correct work is local proof, documentation, tests, prerequisites, and
> architecture hardening. It is not a public launch phase.
>
> This page is the default operating posture until a later status witness
> explicitly promotes the project.

For the step-by-step prerequisite ledger, use
[Foundation Prerequisites](FOUNDATION_PREREQUISITES.md). That page turns broad
setup work into small local evidence items.

---

## Current Posture

| Property | Current value | Boundary |
| --- | --- | --- |
| Work mode | Private foundation work | Build knowledge, structure, docs, local checks, and local proof threads. |
| Operator shape | Solo operator | Prefer slow, explicit, reversible steps over broad execution. |
| Deployment | Local-only unless explicitly approved | Do not assume public API, gateway, DNS, or production health. |
| Product posture | Product direction, not launch | Public wording may describe intent, but must not imply customer readiness. |
| Legal posture | Pre-clearance | Do not claim trademark, patent, compliance, or company readiness. |
| Financial posture | No external spend by default | Avoid paid infrastructure, money movement, or irreversible vendor commitments. |
| Secrets posture | Draft categories only | Do not store real secrets, activate credentials, bind provider accounts, enable external calls, or deploy. |
| Cost/budget posture | Draft categories only | Do not spend, enable billing, bind payment methods, create subscriptions, approve purchases, pay invoices, or deploy. |
| Runtime/environment posture | Draft checks only | Do not claim runtime readiness, start services, activate databases, open endpoints, run migrations, connect cloud runtimes, or deploy. |
| Backup/export posture | Draft plan only | Do not run backups, activate cloud sync, export files, publish archives, delete data, record private paths, move secrets, move personal data, claim restore readiness, or deploy. |
| Proof posture | Repository and local evidence first | Public claims require named witness evidence before promotion. |
| Prerequisite posture | Atomic prerequisite ledger | Prepare one small evidence item at a time; do not create launch pressure. |

## Work Allowed Now

The current phase should favor work that improves structure without creating
external obligations:

1. Write and refine architecture docs, glossary entries, diagrams, and operator
   notes.
2. Add deterministic local tests and schema validators.
3. Build one local proof thread at a time.
4. Improve receipt, audit, evidence, and closure records.
5. Classify prerequisites for later legal, deployment, security, and product
   work.
6. Preserve authorship and invention history through dated repository commits,
   notes, and design records.
7. Keep public-site copy bounded to foundation-stage claims.

## Work Delayed Until Later

These actions are intentionally not first-priority in Foundation Mode:

| Delayed action | Why it waits |
| --- | --- |
| Public deployment | Requires host, DNS, TLS, secrets, database, monitoring, rollback, and witness closure. |
| Customer access | Requires support path, onboarding, terms, privacy, security posture, and recovery plan. |
| Money movement | Requires stronger compliance, approval, audit, liability, and rollback controls. |
| Paid infrastructure | Creates recurring cost before the local proof chain is stable. |
| Company formation | Useful later, but not required for private local architecture hardening. |
| Patent filing | Should wait until the invention boundary and claims are stable enough for qualified review. |
| Fundraising or hiring | Requires clearer product proof, ownership boundary, roadmap, and risk packet. |

## First Local Proof Thread

The safest first proof thread is a local document proof packet:

```text
local request
  -> classify intent
  -> check policy
  -> ask for local approval
  -> create a small document or JSON result
  -> write a receipt
  -> write audit evidence
  -> close with pass/fail status
```

This proves the core structure without external APIs, public deployment, real
payments, or customer exposure.

## Promotion Gates

Do not promote the project out of Foundation Mode until these are true:

| Gate | Required evidence |
| --- | --- |
| Local proof thread | One end-to-end local workflow passes with receipt and audit evidence. |
| Source control | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) keeps staging, commit, push, pull request, release, deployment, and secret publication blocked until explicit request. |
| Documentation | A non-technical reader can understand the current status and next action. |
| Tests | Focused local tests pass for the proof thread and its failure paths. |
| Security | Secrets are absent from docs and fixtures; external calls are disabled by default. |
| Secrets/credentials | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) keeps real secret storage, credential activation, provider binding, key creation, external calls, and deployment blocked. |
| Cost/budget | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) keeps spending, paid infrastructure, provider billing, payment-method binding, subscription creation, purchase approval, invoice payment, vendor commitment, and deployment blocked. |
| Runtime/environment | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) keeps runtime verification, workstation repeatability, dependency-install verification, database activation, container activation, endpoint activation, cloud runtime, migration execution, and deployment blocked. |
| Backup/export | [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) keeps backup execution, cloud backup, external export, public archive, private path recording, secret export, personal-data export, deletion operation, restore-readiness, and deployment blocked. |
| Account recovery | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) keeps owner-only recovery inventory outside Git. |
| Domain and email | [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) keeps DNS mutation, API DNS publication, endpoint readiness, and email deliverability in `AwaitingEvidence`. |
| Product scope | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) selects one local learning lane without restricting the long-term platform or opening pilot/customer claims. |
| Support readiness | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) keeps customer support, SLA, incident readiness, onboarding, paid support, and deployment claims in `AwaitingEvidence`. |
| Intake/onboarding | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) keeps forms, waitlists, pilot signup, personal data collection, CRM import, outreach, onboarding, and paid access closed. |
| Privacy/data | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) keeps personal-data collection, storage, consent capture, tracking, processor activation, privacy publication, legal clearance, customer access, and deployment blocked. |
| Legal readiness | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) keeps trademark, patent, company, tax, terms, compliance, and payment questions in `AwaitingEvidence`. |
| Deployment readiness | `DEPLOYMENT_STATUS.md` remains the authority for public-runtime claims. |
| Prerequisite ledger | `FOUNDATION_PREREQUISITES.md` has no `Blocked` item without a named next evidence action. |

## Default Agent Guidance

When assisting in this repository, assume Foundation Mode unless the user or a
signed status witness says otherwise:

1. Prefer local docs, local tests, local fixtures, and local receipts.
2. Do not push toward deployment, public launch, customers, LLC formation, or
   patent filing.
3. Turn broad ideas into small proof threads.
4. Keep every next step reversible where possible.
5. Label unknowns as `AwaitingEvidence` instead of filling them with optimism.

---

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| Understand the product in plain words | [Plain-English Overview](explain/PLAIN_ENGLISH.md) |
| Turn setup into tiny next steps | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Prepare secrets/credentials safely | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Prepare cost/budget safely | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare runtime/environment safely | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) |
| Prepare backup/export safely | [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Prepare domain/email safely | [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) |
| Prepare product scope safely | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) |
| Prepare support readiness safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare intake/onboarding safely | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| See the current claim boundary | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |
| Look up a confusing word | [Glossary](GLOSSARY.md) |
| See the whole documentation map | [Start Here](START_HERE.md) |

<- Back to [Start Here](START_HERE.md)
