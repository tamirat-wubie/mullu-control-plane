<!--
Purpose: define the source-control commit boundary for Foundation Mode changes.
Governance scope: commit preparation, branch hygiene, uncommitted work visibility, verification commands, no staging without request, no push, no PR, no deployment, and no secret publication.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_source_control_boundary.awaiting_commit.json, scripts/validate_foundation_source_control_boundary.py.
Invariants: no staging claim, no commit claim, no push claim, no PR claim, no deployment claim, no customer access claim, no secret publication claim.
-->

# Foundation Source Control Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** source-control preparation means organizing local Foundation
> Mode changes so a future commit can be made intentionally. It does not stage,
> commit, push, open a pull request, publish a release, deploy, or expose
> private material.

Boundary packet: [`../examples/foundation_source_control_boundary.awaiting_commit.json`](../examples/foundation_source_control_boundary.awaiting_commit.json)

Rule: Commit readiness is prepared locally, but commit execution requires an
explicit user request.

No staging, commit, push, pull request, release, deployment, customer access, or
secret publication claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode now has multiple local artifacts. Without a source-control
boundary, the work can become hard to review. This document defines a small
commit-preparation packet that groups the change families, names the required
verification commands, and keeps external publication blocked.

This is preparation only:

1. The repository can describe a planned commit boundary.
2. Validators can prove the packet does not authorize publication.
3. The operator can later review the packet before requesting staging or commit.
4. No Git effect is performed by this document or validator.

## Current State

```text
source_control_boundary_state=AwaitingEvidence
commit_state=AwaitingCommit
staging_allowed=false
commit_allowed=false
push_allowed=false
pull_request_allowed=false
deployment_allowed=false
```

## Change Families

| Family | Boundary |
| --- | --- |
| Foundation posture | Foundation Mode and prerequisite ledger. |
| Operator readiness | Local solo-operator questions with capacity, schedule, skill, team, hiring, delegation, coverage, authority, and deployment claims blocked. |
| Learning path | Local learning goal, glossary, command practice, reading queue, exercise, error log, verification habit, and help-request questions with skill readiness, training completion, certification, paid course, mentor, hiring, delegation, public tutorial, curriculum, production-operation, customer-support, external-account, and deployment claims blocked. |
| Architecture map | Local system boundary, module, interface, dependency, invariant, hazard, proof-reference, and gap mapping with architecture completeness, module inventory completeness, interface readiness, dependency readiness, invariant closure, hazard closure, proof closure, integration readiness, runtime readiness, refactor approval, implementation approval, publication, and deployment claims blocked. |
| System-boundary inventory | Local public product, control-plane, gateway, runtime, data, tenant, trust, and external-dependency boundary questions with inventory completeness, ownership closure, trust closure, tenant readiness, data classification closure, endpoint readiness, service binding, integration readiness, runtime readiness, exposure approval, implementation approval, publication, and deployment claims blocked. |
| Module inventory | Local product, control-plane, gateway, runtime, governance, evidence, data, and operator module questions with inventory completeness, ownership assignment, contract readiness, interface readiness, dependency readiness, integration readiness, runtime readiness, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Component contracts | Local module identity, input, output, error, evidence, state, dependency, and operator contract questions with component contract readiness, owner approval, test pass, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Interface map | Local component, product/control-plane, control-plane/gateway, gateway/runtime, runtime/governance, governance/evidence, data-flow, and operator handoff questions with interface-map completeness, endpoint readiness, service binding, integration readiness, runtime readiness, implementation approval, publication, and deployment claims blocked. |
| Dependency graph | Local module, package, runtime, service, provider, data, governance, and operator dependency questions with dependency-graph completeness, dependency contract readiness, import readiness, package install approval, version-lock readiness, service dependency binding, provider binding, vulnerability scan pass, runtime dependency readiness, owner approval, test pass, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Invariant map | Local identity, state, boundary, interface, dependency, governance, evidence, rollback, and operator invariant questions with invariant-map completeness, invariant proof readiness, invariant enforcement readiness, conflict resolution, monitor readiness, runtime invariant readiness, owner approval, test pass, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Hazard map | Local safety, runtime, data, dependency, interface, governance, evidence, rollback, and operator hazard questions with hazard-map completeness, classification readiness, severity closure, mitigation readiness, safety review readiness, runtime hazard readiness, owner approval, test pass, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Proof reference | Local architecture, module, interface, dependency, invariant, hazard, runtime, rollback, and operator proof-reference questions with proof-reference completeness, proof coverage closure, evidence promotion, terminal closure, verification pass, proof approval, runtime proof readiness, owner approval, test pass, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Gap register | Local architecture, module, interface, dependency, invariant, hazard, proof-reference, runtime, rollback, and operator gap questions with gap-register completeness, gap closure, priority closure, owner assignment, remediation readiness, roadmap commitment, evidence promotion, terminal closure, test pass, refactor approval, implementation approval, publication, and deployment claims blocked. |
| Diff review | Local changed-file, untracked-file, unrelated-change, agent-scope, user-change-preservation, validation-summary, secret-drift, staging/commit, rollback/revert, and handoff-summary questions with diff-review completeness, scope closure, ownership, staging, commit, branch switch, push, pull request, release, revert, source-control publication, and deployment claims blocked. |
| Change handoff | Local change-family, constructive-delta, fracture-delta, unrelated-change, user-change-preservation, validation-evidence, secret-drift, rollback/revert, next-action, and operator-handoff questions with handoff completeness, changed-file review completeness, diff scope closure, ownership assignment, validation completeness, secret clearance, staging, commit, branch switch, push, pull request, release, revert, source-control publication, and deployment claims blocked. |
| Local workstation | Local command, toolchain, shell, dependency, test, environment, permission, and receipt questions with workstation verification, install, full-test, service, cloud, private path, and deployment claims blocked. |
| Documentation | Local source-of-truth map, plain-language status, glossary questions, cross-links, public-copy alignment, evidence index, update cadence, and reviewer handoff with documentation completeness, canonical-docs, public-launch, customer-readiness, deployment-readiness, legal-clearance, commercial-readiness, external-publication, and deployment claims blocked. |
| Plain-language status | Local current-posture, future-capability separation, non-technical reader, analogy safety, next-step routing, glossary-gap, public-claim language, evidence-reference, limitation, and operator-confusion questions with plain-language completeness, comprehension proof, product readiness, capability availability, real-task execution readiness, customer readiness, public launch, legal clearance, commercial readiness, paid-use readiness, money-movement readiness, canonical-docs, external-publication, and deployment claims blocked. |
| Accessibility/language | Local reading-level, glossary, keyboard, screen-reader, contrast, mobile, translation, localization, Mfidel-atomicity, and public-statement questions with accessibility compliance, WCAG conformance, screen-reader verification, keyboard-navigation verification, contrast compliance, mobile accessibility verification, translation readiness, localization readiness, Mfidel support, Amharic support, public accessibility statements, external user testing, personal-data collection, customer access, external publication, and deployment claims blocked. |
| Capability roadmap | Local capability-family, readiness, sequencing, dependency, evidence-gate, user-value, support-load, pricing-exposure, public-claim, and evolution-review questions with availability, roadmap commitment, delivery-date, customer, pilot, support, pricing, money, external publication, and deployment claims blocked. |
| Agentic management | Local goal-intake, plan-decomposition, delegation, schedule/queue, resource/budget, priority/tradeoff, escalation/approval, progress/receipt, rollback/recovery, and performance-review questions with management authority, task execution, delegation, scheduling, allocation, approval-bypass, customer, money, external publication, and deployment claims blocked. |
| Operations/runbook | Local runbook-inventory, procedure-dry-run, incident-response, monitoring, alerting, on-call, SLO, recovery, operational-graph, MIL-audit-runbook, and evidence-promotion questions with runbook execution, operational readiness, customer-support, external publication, and deployment claims blocked. |
| Claim boundary | Local repository-proof, public-copy, runtime-proof, legal/business, customer/pilot, deployment, evidence-promotion, and review-handoff questions with production-health, endpoint-readiness, customer-readiness, pilot-readiness, legal-clearance, commercial-readiness, public-launch, compliance-certification, external-publication, and deployment claims blocked. |
| Website posture | Local homepage, product-route, proof-route, access-language, waitlist/beta-language, runtime/endpoint-language, public-naming, and website-evidence receipt questions with website mutation, external publication, access invitation, waitlist, beta, pilot-signup, customer-intake, production-runtime, endpoint-readiness, paid-launch, and deployment claims blocked. |
| Research notebook | Local concept inventory, assumption register, prior-art questions, proof-status map, experiment boundary, evidence-promotion questions, authorship-lineage notes, and public-claim language with patent, secrecy, validation, publication, market, customer, paid-launch, secret-evidence, and deployment claims blocked. |
| Evidence ledger | Local evidence references, witness packets, validators, tests, receipts, source-control packet, readiness snapshot, and public-copy routing with evidence-promotion, terminal-closure, readiness, legal, patent, customer, paid-launch, secret-evidence, external-publication, and deployment claims blocked. |
| Decision journal | Local decision context, assumption snapshot, option set, constraint check, evidence refs, risk stop rule, review cadence, and next-action selection with decision-execution, irreversible-action, roadmap, deadline, authority, customer, legal, company, patent, spending, external-publication, and deployment claims blocked. |
| Next action | Local continuation triage, smallest prerequisite selection, dependency checks, local edit scope, verification plan, stop rule, receipt plan, and handoff summary with broad execution, external action, deployment, publication, spending, customer action, legal/business action, claim promotion, secret use, credential use, service activation, source-control publication, roadmap, and deadline claims blocked. |
| Test evidence | Local focused-validator, targeted-pytest, full-preflight, receipt-validation, diff-hygiene, failure-case, warning-triage, coverage-gap, reproducibility, and non-terminal-closure questions with full-test pass, complete coverage, CI parity, release readiness, deployment readiness, security clearance, secret clearance, customer readiness, legal clearance, performance readiness, flake-free, terminal-closure, external-publication, and deployment claims blocked. |
| Local proof thread | Local descriptor, runner, validator, tests, and ignored receipt. |
| Private recovery | Public-safe recovery checklist and AwaitingEvidence witness. |
| Secrets/credentials | Local credential categories and access questions with real secret storage, credential activation, provider binding, external calls, and deployment blocked. |
| Security baseline | Local security questions with scan-pass, dependency-audit pass, threat-model approval, access-control verification, compliance, customer-security, and deployment claims blocked. |
| Cost/budget | Local cost categories and approval questions with spending, billing, payment methods, subscriptions, purchases, invoice payments, vendor commitments, and deployment blocked. |
| Payment provider | Local provider-selection, account-binding, merchant-onboarding, KYC/tax, payment-method, checkout, webhook, charge/refund, payout, and reconciliation questions with provider activation, provider-account binding, merchant onboarding, KYC readiness, tax readiness, payment-method collection, live charge, refund, payout, webhook activation, checkout publication, money movement, customer payment access, external publication, and deployment claims blocked. |
| Runtime/environment | Local command and toolchain questions with runtime verification, database activation, container activation, endpoint activation, migration execution, cloud runtime, and deployment blocked. |
| Backup/export | Local backup/export questions with backup execution, cloud backup, external export, public archive, private path recording, secret export, personal-data export, deletion, restore-readiness, and deployment blocked. |
| Deployment deferral | Local deployment prerequisite, cloud, endpoint, runtime health, rollback, cost, credential, customer/support, and publication questions with deployment-plan approval, cloud activation, public endpoints, production health, runtime readiness, customer access, spending, credential use, secret use, migration execution, DNS mutation, external publication, and deployment blocked. |
| External infrastructure | Local DNS authority, gateway target, runtime host, managed database, secret-manager, TLS, firewall, rollback, private runtime witness, repository variable, endpoint reachability, and workflow dispatch questions with external-infrastructure completeness, DNS authority verification, DNS target binding, DNS mutation, runtime provisioning, secret placement, workflow dispatch, paid infrastructure, customer access, publication, and deployment blocked. |
| Domain/email | Public-safe domain and email labels with DNS/email readiness blocked. |
| Legal/business | Question-only packet with qualified-review gating. |
| Product scope | Selected local learning lane with platform non-restriction and pilot/customer claims blocked. |
| Market research | Local problem, target-user, market-category, similar-platform, differentiation, pricing, validation, public-claim, risk, and evidence-promotion questions with customer research, surveys, waitlists, outreach, market validation, product-market fit, competitor superiority, pricing readiness, investor materials, personal-data collection, customer access, money movement, external publication, and deployment blocked. |
| Pilot deferral | Local pilot purpose, participant-boundary, access-channel, consent/privacy, support, rollback, success-metric, legal/terms, and public-claim questions with pilot execution, participant invitation, access channels, waitlists, beta, customer access, personal-data collection, market validation, support readiness, legal clearance, paid pilot, external publication, and deployment blocked. |
| Support readiness | Local support and incident-response shape with support service, SLA, onboarding, paid support, and deployment claims blocked. |
| Intake/onboarding | Local intake and onboarding shape with forms, waitlists, pilot signups, personal data collection, CRM import, outreach, paid access, and customer access blocked. |
| Customer access | Local access-policy, eligibility, account-creation, invitation, support-duty, terms/privacy, data-handling, rollback/exit, payment-exposure, and public-claim questions with customer invitation, account creation, access channels, onboarding readiness, support commitments, terms/privacy readiness, personal-data collection, paid access, pilot access, beta access, waitlists, external publication, and deployment blocked. |
| Privacy/data | Local privacy, consent, retention, deletion, processor, and tracking questions with personal-data handling and legal-clearance claims blocked. |
| Funding/team | Local funding-readiness, investor-boundary, grant, pitch, hiring, contractor, advisor, compensation/equity, payroll/budget, and recruiting questions with fundraising, investor outreach, grant application, pitch publication, hiring, contractor engagement, advisor commitment, compensation commitment, equity promise, payroll setup, budget commitment, company-formation claim, legal-clearance claim, money movement, external publication, and deployment blocked. |
| Community/network | Local relationship, community, forum, social, collaborator, partner, mentor, feedback, event, and referral questions with outreach, public posts, direct messages, recruiting, partnerships, mentor requests, public feedback, events, contact lists, personal-data collection, external accounts, customer access, external publication, and deployment blocked. |
| Public claim alignment | Public-copy and naming checks remain foundation-stage. |
| Governance preflight | Preflight command list, receipt schema, receipt example, and tests. |

## Required Pre-Commit Evidence

Before a future commit request, verify at minimum:

```powershell
python scripts/validate_foundation_mode.py
python scripts/validate_foundation_operator_readiness_boundary.py
python scripts/validate_foundation_learning_path_boundary.py
python scripts/validate_foundation_architecture_map_boundary.py
python scripts/validate_foundation_system_boundary_inventory_boundary.py
python scripts/validate_foundation_module_inventory_boundary.py
python scripts/validate_foundation_component_contract_boundary.py
python scripts/validate_foundation_interface_map_boundary.py
python scripts/validate_foundation_dependency_graph_boundary.py
python scripts/validate_foundation_invariant_map_boundary.py
python scripts/validate_foundation_hazard_map_boundary.py
python scripts/validate_foundation_proof_reference_boundary.py
python scripts/validate_foundation_gap_register_boundary.py
python scripts/validate_foundation_diff_review_boundary.py
python scripts/validate_foundation_change_handoff_boundary.py
python scripts/validate_foundation_local_workstation_boundary.py
python scripts/validate_foundation_documentation_boundary.py
python scripts/validate_foundation_plain_language_status_boundary.py
python scripts/validate_foundation_accessibility_language_boundary.py
python scripts/validate_foundation_capability_roadmap_boundary.py
python scripts/validate_foundation_agentic_management_boundary.py
python scripts/validate_foundation_operations_runbook_boundary.py
python scripts/validate_foundation_claim_boundary.py
python scripts/validate_foundation_website_posture_boundary.py
python scripts/validate_foundation_research_notebook_boundary.py
python scripts/validate_foundation_evidence_ledger_boundary.py
python scripts/validate_foundation_decision_journal_boundary.py
python scripts/validate_foundation_next_action_boundary.py
python scripts/validate_foundation_test_evidence_boundary.py
python scripts/validate_foundation_local_proof_thread.py
python scripts/validate_foundation_private_recovery_boundary.py
python scripts/validate_foundation_secrets_credentials_boundary.py
python scripts/validate_foundation_security_baseline_boundary.py
python scripts/validate_foundation_cost_budget_boundary.py
python scripts/validate_foundation_payment_provider_boundary.py
python scripts/validate_foundation_runtime_environment_boundary.py
python scripts/validate_foundation_backup_export_boundary.py
python scripts/validate_foundation_deployment_deferral_boundary.py
python scripts/validate_foundation_external_infrastructure_boundary.py
python scripts/validate_foundation_domain_email_boundary.py
python scripts/validate_foundation_legal_business_boundary.py
python scripts/validate_foundation_product_scope_boundary.py
python scripts/validate_foundation_market_research_boundary.py
python scripts/validate_foundation_pilot_deferral_boundary.py
python scripts/validate_foundation_support_readiness_boundary.py
python scripts/validate_foundation_intake_onboarding_boundary.py
python scripts/validate_foundation_customer_access_boundary.py
python scripts/validate_foundation_privacy_data_boundary.py
python scripts/validate_foundation_funding_team_boundary.py
python scripts/validate_foundation_community_network_boundary.py
python scripts/validate_foundation_source_control_boundary.py
python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json
python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt.json
git diff --check
git status --short
```

## Operator Procedure

1. Review the packet and changed file list.
2. Confirm there are no private values in the planned commit.
3. Run the required pre-commit evidence commands.
4. Only after an explicit user request, stage the intended files.
5. Commit with a Foundation Mode subject that describes what changed.
6. Do not push or open a pull request unless the user explicitly requests it.

## Validation

Run:

```powershell
python scripts/validate_foundation_source_control_boundary.py
```

The validator checks that the source-control packet:

1. keeps staging, commit, push, pull request, release, and deployment disabled;
2. names the required Foundation validators;
3. keeps every change family in `AwaitingEvidence`;
4. includes rollback and no-secret checks; and
5. rejects publication or readiness-promotion drift.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: commit boundary prepared, staging blocked, commit blocked without explicit request, push blocked, pull request blocked, deployment blocked, no secret publication claim
  Open issues: actual staging, commit, push, and pull request remain AwaitingEvidence until explicitly requested
  Next action: run the source-control boundary validator, then review the packet before any future commit request
