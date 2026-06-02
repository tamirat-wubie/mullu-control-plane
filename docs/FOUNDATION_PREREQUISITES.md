<!--
Purpose: define the atomic prerequisite ladder for solo-founder Foundation Mode.
Governance scope: local setup, evidence readiness, claim boundaries, legal/business separation, deployment restraint, and reversible next actions.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md, docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md, docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md, docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md, docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md, docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md, docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md, docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md, docs/FOUNDATION_CLAIM_BOUNDARY.md, docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md, docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md, docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md, docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md, docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md, docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md, docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md, docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md, docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md, docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_LOCAL_PROOF_THREAD.md, docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md, docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md, docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md, docs/START_HERE.md, docs/CURRENT_READINESS_SNAPSHOT.md, DEPLOYMENT_STATUS.md, AGENTS.md.
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
| Operator readiness | Draft questions only | Use [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) to draft solo capacity, pacing, skill-gap, learning-loop, decision-authority, escalation, stop-rule, and review-cadence questions locally. | Do not claim capacity, schedule, skill, team, hiring, delegation, incident coverage, support coverage, legal authority, financial authority, or deployment readiness. | Operator-readiness witness and local draft checklist. |
| Learning path | Local practice loops only | Use [Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md) to draft learning goal, glossary, command practice, reading queue, local exercise, error log, verification habit, and help-request boundary questions locally. | Do not claim skill readiness, training completion, certification, paid-course activation, mentor assignment, hiring readiness, delegation readiness, public tutorial publication, curriculum completion, production-operation readiness, customer-support readiness, external account use, or deployment readiness. | Learning-path witness and local draft checklist. |
| Architecture map | Local structure mapping only | Use [Foundation Architecture Map Boundary](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md) to draft system boundary, module inventory, interface map, dependency graph, invariant map, hazard map, proof-reference, and gap-register questions locally. | Do not claim architecture completeness, module inventory completeness, interface contract readiness, dependency graph readiness, invariant closure, hazard closure, proof coverage closure, integration readiness, runtime readiness, refactor approval, implementation approval, external publication, or deployment readiness. | Architecture-map witness and local draft checklist. |
| System-boundary inventory | Local boundary questions only | Use [Foundation System Boundary Inventory Boundary](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md) to draft public product, control-plane, gateway, runtime, data, tenant, trust, and external-dependency boundary questions locally. | Do not claim system-boundary inventory completeness, ownership closure, trust closure, tenant readiness, data classification closure, endpoint readiness, service binding, integration readiness, runtime readiness, exposure approval, implementation approval, external publication, or deployment readiness. | System-boundary inventory witness and local draft checklist. |
| Module inventory | Local module questions only | Use [Foundation Module Inventory Boundary](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md) to draft product, control-plane, gateway, runtime, governance, evidence, data, and operator module questions locally. | Do not claim module inventory completeness, ownership assignment, contract readiness, interface readiness, dependency readiness, integration readiness, runtime readiness, refactor approval, implementation approval, external publication, or deployment readiness. | Module-inventory witness and local draft checklist. |
| Component contracts | Local contract questions only | Use [Foundation Component Contract Boundary](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md) to draft module identity, input, output, error, evidence, state, dependency, and operator contract questions locally. | Do not claim component contract readiness, input readiness, output readiness, error readiness, evidence readiness, state readiness, dependency readiness, owner approval, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Component-contract witness and local draft checklist. |
| Interface map | Local relationship questions only | Use [Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md) to draft component, product/control-plane, control-plane/gateway, gateway/runtime, runtime/governance, governance/evidence, data-flow, and operator handoff questions locally. | Do not claim interface-map completeness, interface contract readiness, endpoint readiness, service binding, event/message readiness, data-flow readiness, trust closure, integration readiness, runtime readiness, owner approval, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Interface-map witness and local draft checklist. |
| Dependency graph | Local dependency questions only | Use [Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md) to draft module, package, runtime, service, provider, data, governance, and operator dependency questions locally. | Do not claim dependency-graph completeness, dependency contract readiness, import readiness, package install approval, version-lock readiness, service dependency binding, provider binding, vulnerability scan pass, runtime dependency readiness, owner approval, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Dependency-graph witness and local draft checklist. |
| Invariant map | Local invariant questions only | Use [Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md) to draft identity, state, boundary, interface, dependency, governance, evidence, rollback, and operator invariant questions locally. | Do not claim invariant-map completeness, invariant proof readiness, invariant enforcement readiness, invariant conflict resolution, invariant monitor readiness, runtime invariant readiness, owner approval, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Invariant-map witness and local draft checklist. |
| Hazard map | Local hazard questions only | Use [Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md) to draft safety, runtime, data, dependency, interface, governance, evidence, rollback, and operator hazard questions locally. | Do not claim hazard-map completeness, hazard classification readiness, hazard severity closure, mitigation readiness, safety review readiness, runtime hazard readiness, owner approval, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Hazard-map witness and local draft checklist. |
| Proof reference | Local proof questions only | Use [Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md) to draft architecture, module, interface, dependency, invariant, hazard, runtime, rollback, and operator proof-reference questions locally. | Do not claim proof-reference completeness, proof coverage closure, evidence promotion, terminal closure, verification pass, proof approval, runtime proof readiness, owner approval, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Proof-reference witness and local draft checklist. |
| Gap register | Local gap questions only | Use [Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md) to draft architecture, module, interface, dependency, invariant, hazard, proof-reference, runtime, rollback, and operator gap questions locally. | Do not claim gap-register completeness, gap closure, priority closure, owner assignment, remediation readiness, roadmap commitment, evidence promotion, terminal closure, test pass, refactor approval, implementation approval, external publication, or deployment readiness. | Gap-register witness and local draft checklist. |
| Diff review | Local worktree review questions only | Use [Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md) to draft changed-file, untracked-file, unrelated-change, agent-scope, user-change preservation, validation-summary, secret-drift, staging/commit, rollback/revert, and handoff-summary questions locally. | Do not claim diff-review completeness, diff scope closure, ownership assignment, staging approval, commit approval, branch switch approval, push approval, pull request approval, release readiness, revert approval, test pass, source-control publication, external publication, or deployment readiness. | Diff-review witness and local draft checklist. |
| Change handoff | Local handoff questions only | Use [Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md) to draft change-family, constructive-delta, fracture-delta, unrelated-change, user-change preservation, validation-evidence, secret-drift, rollback/revert, next-action, and operator-handoff questions locally. | Do not claim change-handoff completeness, changed-file review completeness, diff scope closure, ownership assignment, validation completeness, secret clearance, staging approval, commit approval, branch switch approval, push approval, pull request approval, release readiness, revert approval, source-control publication, external publication, or deployment readiness. | Change-handoff witness and local draft checklist. |
| Source control | Local repository work | Use [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) to keep clean diffs, meaningful commits, branch boundaries, and no-secret checks explicit. | Do not publish sensitive internals. | Git status, commit messages, PR summaries. |
| Local workstation | Draft questions only | Use [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) to draft command, toolchain, shell/profile, dependency-install, test-command, environment-variable, permission, and local-receipt questions locally. | Do not verify the workstation, install dependencies, mutate environment, start services, claim full-test pass, depend on cloud, record private paths, or deploy. | Local-workstation witness and local draft checklist. |
| Documentation | Draft navigation only | Use [Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md) to draft source-of-truth map, plain-language status, glossary questions, prerequisite cross-links, public-copy alignment, evidence index, update cadence, and reviewer handoff locally. | Do not claim documentation completeness, canonical docs, public-launch copy, customer readiness, deployment readiness, legal clearance, commercial readiness, external publication, or deployment. | Documentation witness and local draft checklist. |
| Plain-language status | Non-technical explanation only | Use [Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md) to draft current-posture, future-capability separation, reader-question, analogy, routing, glossary-gap, public-claim, evidence-reference, limitation, and operator-confusion questions locally. | Do not claim plain-language completeness, comprehension proof, product readiness, capability availability, real-task execution readiness, customer readiness, public launch, legal clearance, commercial readiness, paid-use readiness, money-movement readiness, canonical docs, external publication, or deployment. | Plain-language status witness and local draft checklist. |
| Claim boundary | Foundation-stage separation only | Use [Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md) to separate repository proof, public copy, runtime proof, legal/business claims, customer/pilot claims, deployment claims, evidence-promotion questions, and claim-review handoff locally. | Do not claim production health, endpoint readiness, customer readiness, pilot readiness, legal clearance, commercial readiness, public launch, compliance certification, external publication, or deployment. | Claim-boundary witness and local draft checklist. |
| Research notebook | Local concept organization only | Use [Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md) to draft concept inventory, assumption register, prior-art questions, proof-status map, experiment boundary, evidence-promotion questions, authorship-lineage notes, and public-claim language locally. | Do not claim patent protection, trade-secret protection, scientific validation, physical-world validation, market validation, customer readiness, external publication, paid launch, secret evidence, or deployment readiness. | Research-notebook witness and local draft checklist. |
| Market research | Local comparison questions only | Use [Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md) to draft problem-hypothesis, target-user, market-category, similar-platform, differentiation, pricing, validation-plan, public-claim, risk-obligation, and evidence-promotion questions locally. | Do not run customer research, publish surveys, open waitlists, start outreach, claim market validation, claim product-market fit, claim category readiness, claim market size, claim competitor superiority, publish benchmarks, claim pricing readiness, publish public offers, create investor materials, collect personal data, open customer access, move money, publish externally, or deploy. | Market-research witness and local draft checklist. |
| Evidence ledger | Local evidence-reference organization only | Use [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) to draft boundary-doc, witness-packet, validator, test, preflight-receipt, source-control-packet, readiness-snapshot, and public-copy-routing references locally. | Do not promote evidence, claim terminal closure, claim readiness, claim legal clearance, claim patent protection, claim customer readiness, launch paid use, record secret evidence, publish externally, or deploy. | Evidence-ledger witness and local draft checklist. |
| Decision journal | Local decision-context organization only | Use [Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md) to draft decision context, assumption snapshot, option set, constraint check, evidence references, risk stop rule, review cadence, and next-action selection locally. | Do not execute decisions, authorize irreversible action, commit to a roadmap, promise deadlines, delegate authority, make customer commitments, claim legal authority, form a company, file a patent, spend money, publish externally, or deploy. | Decision-journal witness and local draft checklist. |
| Next action | Local continuation triage only | Use [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) to keep `continue` work to one local-safe prerequisite, dependency check, verification plan, stop rule, receipt plan, and handoff summary. | Do not execute broad continuation, cross external boundaries, deploy, publish, spend, contact customers, take legal/business action, promote claims, use secrets or credentials, activate services, publish source control, commit to a roadmap, or promise deadlines. | Next-action witness and local draft checklist. |
| Test evidence | Local validation-scope recording only | Use [Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md) to record focused validators, targeted pytest, preflight, receipt validation, diff hygiene, failure cases, warnings, coverage gaps, reproducibility notes, and non-terminal closure locally. | Do not claim full-test pass, complete coverage, CI parity, release readiness, security clearance, customer readiness, legal clearance, external publication, or deployment. | Test-evidence witness and local draft checklist. |
| Security basics | Draft questions only | Use [Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md) to draft threat-model, dependency-audit, static-scan, access-control, data-exposure, supply-chain, and review-readiness questions locally. | Do not claim scan pass, dependency audit pass, threat-model approval, access-control verification, compliance certification, customer-security readiness, or deployment readiness. | Security-baseline witness and local draft checklist. |
| Secrets/credentials | Draft categories only | Use [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) to draft credential categories, environment-variable names, provider-access questions, key questions, and rotation questions locally. | Do not store real secrets, activate credentials, bind provider accounts, enable external calls, or commit environment files. | Secrets/credentials witness and local draft checklist. |
| Cost/budget | No spend by default | Use [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) to draft cost categories, budget questions, billing questions, payment-method questions, subscription questions, and purchase controls locally. | Do not spend, enable billing, bind payment methods, create subscriptions, approve purchases, pay invoices, or activate paid infrastructure. | Cost/budget witness and local draft checklist. |
| Payment provider | Local simulation questions only | Use [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md) to draft provider-selection, account-binding, merchant-onboarding, KYC/tax, payment-method, checkout, webhook, charge/refund, payout, and reconciliation questions locally. | Do not activate payment providers, bind provider accounts, complete merchant onboarding, claim KYC/tax readiness, collect payment methods, process live charges, execute refunds, settle payouts, activate webhooks, publish checkout, move money, open customer payment access, publish externally, or deploy. | Payment-provider witness and local draft checklist. |
| Runtime/environment | Draft checks only | Use [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) to draft local command, toolchain, dependency, database, container, endpoint, migration, and rollback questions. | Do not claim runtime readiness, start services, activate databases, open endpoints, connect cloud runtimes, run migrations, or deploy. | Runtime/environment witness and local draft checklist. |
| Backup/export | Draft plan only | Use [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) to draft backup inventory, export scope, archive, restore-drill, redaction, retention, deletion, and handoff questions locally. | Do not run backups, activate cloud sync, export files, publish archives, delete data, record private paths, move secrets, move personal data, claim restore readiness, or deploy. | Backup/export witness and local draft checklist. |
| Account recovery | Needs private owner evidence | Use [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) to create a private recovery inventory outside public docs. | Do not store recovery codes or account secrets in this repo. | Private inventory reference, not secret content. |
| Domain and email | Existing public identity, incomplete readiness evidence | Use [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) to record DNS/email posture in public-safe witness form. | Do not expose provider account IDs or private DNS targets. | Public-safe DNS/email witness notes. |
| Legal/business | Pre-clearance | Use [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) to separate trademark, company, tax, patent, terms, compliance, and payment questions. | Do not claim legal clearance, patent protection, or company readiness. | Questions list and qualified-review TODOs. |
| Product scope | Product direction | Use [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) to select one local learning lane while preserving the broader platform direction. | Do not market broad platform promises or treat the lane as a pilot. | Product-scope witness and one proof-thread goal. |
| Support readiness | Support direction | Use [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) to draft support, triage, incident, rollback, and closure surfaces locally. | Do not open support, promise response time, claim incident readiness, or start onboarding. | Support-readiness witness and local draft checklist. |
| Intake/onboarding | Future intake direction | Use [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) to draft intake fields, consent questions, onboarding steps, and retention questions locally. | Do not publish forms, open waitlists, accept pilot signups, collect personal data, import CRM records, start outreach, or onboard customers. | Intake/onboarding witness and local draft checklist. |
| Customer access | Local access questions only | Use [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) to draft access-policy, eligibility, account-creation, invitation, support-duty, terms/privacy, data-handling, rollback/exit, payment-exposure, and public-claim questions locally. | Do not invite customers, create accounts, open access channels, claim onboarding readiness, make support commitments, claim terms/privacy readiness, collect personal data, accept paid access, open pilot/beta/waitlist access, publish externally, or deploy. | Customer-access witness and local draft checklist. |
| Privacy/data | Data handling direction | Use [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) to draft privacy, consent, retention, deletion, processor, tracking, and minimization questions locally. | Do not collect or store personal data, publish privacy notices, capture consent, enable tracking, activate processors, or claim legal clearance. | Privacy/data witness and local draft checklist. |
| Funding/team | Local questions only | Use [Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md) to draft funding-readiness, investor-boundary, grant, pitch, hiring, contractor, advisor, compensation/equity, payroll/budget, and recruiting questions locally. | Do not fundraise, contact investors, submit grants, publish pitches, hire, engage contractors, commit advisors, promise compensation or equity, set up payroll, commit budgets, claim company formation, claim legal clearance, move money, publish externally, or deploy. | Funding/team witness and local draft checklist. |
| Community/network | Local relationship questions only | Use [Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md) to draft personal-network, community-channel, help-request, forum-post, social-post, collaborator, partnership, mentor, feedback, event, and referral questions locally. | Do not post publicly, contact people, send messages, ask for feedback, recruit collaborators, approach partners, request mentors, register for events, store contact lists, collect personal data, use external accounts, open customer access, publish externally, or deploy. | Community/network witness and local draft checklist. |
| Local proof thread | Descriptor, validator, and local runner prepared | Use [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md) to keep the first workflow local, approval-gated, receipt-bound, and rollback-named. | Do not connect real payments, users, or public endpoints. | Workflow descriptor, validator output, local result, receipt, audit, rollback note. |
| Website posture | Local review only | Use [Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md) to draft homepage, product-route, proof-route, access-language, waitlist/beta-language, runtime/endpoint-language, public-naming, and website-evidence receipt questions locally. | Do not mutate website files, publish routes, invite access, open waitlists, open beta, accept pilot signups, collect customer intake, claim production runtime, claim endpoint readiness, launch paid use, or deploy. | Website-posture witness and local draft checklist. |
| Deployment deferral | Delayed by design | Use [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) to draft deployment prerequisite, cloud, endpoint, runtime health, rollback, cost, credential, customer/support, and publication questions locally. | Do not approve a deployment plan, activate cloud resources, open public endpoints, claim production health, claim runtime readiness, invite customers, spend money, use credentials, mutate DNS, publish externally, or deploy. | Deployment-deferral witness and local draft checklist. |
| External infrastructure | Local prerequisite questions only | Use [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) to draft DNS authority, gateway target, runtime host, managed database, secret-manager, TLS, firewall, rollback, private runtime witness, repository variable, endpoint reachability, and workflow dispatch questions locally. | Do not claim external-infrastructure completeness, verify DNS authority, bind DNS targets, mutate DNS, provision runtime hosts, provision databases, verify secret placement, claim endpoint reachability, bind repository variables, dispatch workflows, activate paid infrastructure, open customer access, publish externally, or deploy. | External-infrastructure witness and local draft checklist. |
| Pilot deferral | Delayed by design | Use [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md) to draft pilot purpose, participant-boundary, access-channel, consent/privacy, support, rollback, success-metric, legal/terms, and public-claim questions locally. | Do not execute a pilot, invite participants, open access channels, open waitlists, open beta, collect personal data, claim market validation, promise support, claim legal clearance, accept payment, publish externally, or deploy. | Pilot-deferral witness and local draft checklist. |

## Recommended Order

1. Keep the current Foundation Mode boundary intact.
2. Prepare operator-readiness notes using [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md).
3. Prepare learning-path notes using [Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md).
4. Prepare architecture-map notes using [Foundation Architecture Map Boundary](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md).
5. Prepare system-boundary inventory notes using [Foundation System Boundary Inventory Boundary](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md).
6. Prepare module-inventory notes using [Foundation Module Inventory Boundary](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md).
7. Prepare component-contract notes using [Foundation Component Contract Boundary](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md).
8. Prepare interface-map notes using [Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md).
9. Prepare dependency-graph notes using [Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md).
10. Prepare invariant-map notes using [Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md).
11. Prepare hazard-map notes using [Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md).
12. Prepare proof-reference notes using [Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md).
13. Prepare gap-register notes using [Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md).
14. Prepare diff-review notes using [Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md).
15. Prepare change-handoff notes using [Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md).
16. Prepare local-workstation notes using [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md).
17. Prepare documentation-navigation notes using [Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md).
18. Prepare plain-language status notes using [Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md).
19. Prepare claim-boundary notes using [Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md).
20. Prepare website-posture notes using [Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md).
21. Prepare research-notebook notes using [Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md).
22. Prepare market-research notes using [Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md).
23. Prepare evidence-ledger notes using [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md).
24. Prepare decision-journal notes using [Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md).
25. Prepare next-action selection using [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md).
26. Prepare test-evidence notes using [Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md).
27. Close source-control hygiene: commit boundary, branch boundary, and no secret drift using [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md).
28. Prepare secrets/credentials notes using [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md).
29. Prepare security-baseline notes using [Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md).
30. Prepare cost/budget notes using [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md).
31. Prepare payment-provider questions using [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md).
32. Prepare runtime/environment notes using [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md).
33. Prepare backup/export notes using [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md).
34. Keep deployment deferred using [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md).
35. Prepare external-infrastructure notes using [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md).
36. Close one local proof thread with a receipt and rollback note.
37. Prepare private recovery inventory outside the repository using [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md).
38. Prepare domain/email public-safe witness notes using [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md).
39. Prepare product-scope learning lane notes using [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md).
40. Prepare support-readiness notes using [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md).
41. Prepare intake/onboarding notes using [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md).
42. Prepare customer-access questions using [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md).
43. Prepare privacy/data notes using [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md).
44. Prepare legal/business questions without making legal claims using [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md).
45. Prepare funding/team questions using [Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md).
46. Prepare community/network questions without outreach using [Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md).
47. Keep pilot deferred using [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md).
48. Reassess whether deployment or pilot prerequisites should even start.

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
| Security baseline | Can create false trust, compliance, or customer-readiness claims. | Use [Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md); never claim scan pass, dependency safety, threat-model approval, compliance, customer-security readiness, or deployment from draft planning. |
| Cost and budget | Can create recurring spend or irreversible vendor obligations. | Use [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md); never bind payment methods or approve purchases in Foundation Mode. |
| Payment providers | Can create money movement, merchant obligations, customer trust duties, tax/KYC duties, webhook secrets, and irreversible financial records. | Use [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md); simulate locally only, never bind providers, collect payment methods, process payments, publish checkout, open customer payment access, move money, publish externally, or deploy from draft planning. |
| Runtime and environment | Can create false readiness, state changes, or endpoint exposure. | Use [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md); never claim runtime readiness or deploy from draft checks. |
| Backup and export | Can expose private paths, secrets, personal records, or incomplete restore claims. | Use [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md); never run backups, cloud sync, exports, public archives, deletion, or restore claims from draft planning. |
| Deployment deferral | Can create public exposure, cloud bills, support duties, and false trust. | Use [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md); keep deployment delayed until later witness evidence promotes one exact bounded step. |
| External infrastructure | Can create DNS exposure, paid runtime obligations, secret-placement risk, and false endpoint readiness. | Use [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md); never mutate DNS, provision runtime, bind repository variables, dispatch workflows, expose endpoints, spend money, or deploy from draft planning. |
| Pilot deferral | Can create participant trust duties, support load, privacy risk, and premature market claims. | Use [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md); keep pilot access closed until later witness evidence promotes one exact bounded step. |
| Market research | Can create false customer, pricing, investor, or demand claims if local comparison notes are treated as evidence. | Use [Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md); draft locally only, never publish surveys, open waitlists, start outreach, claim validation, collect personal data, publish offers, move money, or deploy from planning. |
| Legal/business filings | Create obligations and public claims. | Prepare questions; get qualified review later. |
| Customer access | Creates support, safety, privacy, legal, recovery, billing, and trust duties. | Use [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md); draft locally only, never invite customers, create accounts, open access channels, collect personal data, accept paid access, open pilot/beta/waitlist access, publish externally, or deploy from planning. |
| Funding/team | Creates investor, employment, contractor, advisor, payroll, equity, budget, and roadmap obligations. | Use [Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md); draft locally only, never contact investors, submit grants, publish pitches, hire, engage contractors, promise equity, set payroll, move money, publish externally, or deploy from planning. |
| Community/network | Creates public expectation, privacy, support, collaboration, and reputation obligations. | Use [Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md); draft locally only, never post publicly, message people, ask for feedback, recruit, partner, request mentors, register for events, store contact lists, collect personal data, publish externally, or deploy from planning. |

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
| Prepare operator readiness without readiness claims | [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) |
| Prepare learning loops without readiness claims | [Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md) |
| Prepare architecture mapping without readiness claims | [Foundation Architecture Map Boundary](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md) |
| Prepare system-boundary inventory without readiness claims | [Foundation System Boundary Inventory Boundary](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md) |
| Prepare module inventory without readiness claims | [Foundation Module Inventory Boundary](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md) |
| Prepare component contracts without readiness claims | [Foundation Component Contract Boundary](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md) |
| Prepare interface maps without readiness claims | [Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md) |
| Prepare dependency graphs without readiness claims | [Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md) |
| Prepare invariant maps without readiness claims | [Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md) |
| Prepare hazard maps without readiness claims | [Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md) |
| Prepare proof references without coverage or closure claims | [Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md) |
| Prepare gap registers without closure or roadmap claims | [Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md) |
| Prepare diff review without Git effects | [Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md) |
| Prepare change handoff without approval claims | [Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md) |
| Prepare local workstation without repeatability claims | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Prepare documentation without readiness claims | [Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md) |
| Prepare plain-language status without readiness claims | [Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md) |
| Prepare claim boundaries without promotion | [Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md) |
| Prepare website posture without publication | [Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md) |
| Prepare research notebook without patent, secrecy, validation, publication, market, or customer claims | [Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md) |
| Prepare market research without validation or outreach | [Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md) |
| Prepare evidence ledger without evidence promotion or closure claims | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Prepare decision journal without commitments or external action | [Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md) |
| Choose one next local action without broad execution | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |
| Record test evidence without readiness or coverage claims | [Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md) |
| Prepare source-control commit boundary | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Prepare secrets/credentials without live credentials | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Prepare security baseline without readiness claims | [Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md) |
| Prepare cost/budget without spending | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare payment-provider questions without money movement | [Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md) |
| Prepare runtime/environment without deployment | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) |
| Prepare backup/export without moving data | [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) |
| Keep deployment deferred without exposure | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |
| Prepare external infrastructure without activation | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Prepare owner-only recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Prepare domain/email public-safe witness | [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) |
| Prepare product scope without restricting the platform | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) |
| Prepare support readiness without opening support | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare intake/onboarding without opening access | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare privacy/data without handling people data | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Prepare customer access without opening access | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Prepare funding/team without obligations | [Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md) |
| Prepare community/network without outreach | [Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md) |
| Keep pilot deferred without access | [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md) |
| See current public claim truth | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |
| Start from the front door | [Start Here](START_HERE.md) |
| Check runtime publication truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |
| Understand terms | [Glossary](GLOSSARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: local proof first, reversible steps, no deployment claim, no customer access claim, no legal conclusion
  Open issues: operator-readiness evidence, learning-path evidence, architecture-map evidence, system-boundary inventory evidence, module-inventory evidence, component-contract evidence, interface-map evidence, dependency-graph evidence, invariant-map evidence, hazard-map evidence, proof-reference evidence, gap-register evidence, diff-review evidence, change-handoff evidence, local-workstation evidence, documentation evidence, plain-language status evidence, claim-boundary evidence, website-posture evidence, research-notebook evidence, market-research evidence, evidence-ledger evidence, decision-journal evidence, next-action evidence, secrets/credentials evidence, security-baseline evidence, cost/budget evidence, payment-provider evidence, runtime/environment evidence, backup/export evidence, deployment-deferral evidence, external-infrastructure evidence, pilot-deferral evidence, private recovery evidence, support evidence, intake/onboarding evidence, privacy/data evidence, customer-access evidence, funding/team evidence, community/network evidence, legal review, and runtime witness remain AwaitingEvidence
  Next action: pick one ledger row and close one local evidence item
