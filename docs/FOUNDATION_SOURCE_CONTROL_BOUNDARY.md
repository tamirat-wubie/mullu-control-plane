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
| Local proof thread | Local descriptor, runner, validator, tests, and ignored receipt. |
| Private recovery | Public-safe recovery checklist and AwaitingEvidence witness. |
| Secrets/credentials | Local credential categories and access questions with real secret storage, credential activation, provider binding, external calls, and deployment blocked. |
| Cost/budget | Local cost categories and approval questions with spending, billing, payment methods, subscriptions, purchases, invoice payments, vendor commitments, and deployment blocked. |
| Runtime/environment | Local command and toolchain questions with runtime verification, database activation, container activation, endpoint activation, migration execution, cloud runtime, and deployment blocked. |
| Backup/export | Local backup/export questions with backup execution, cloud backup, external export, public archive, private path recording, secret export, personal-data export, deletion, restore-readiness, and deployment blocked. |
| Domain/email | Public-safe domain and email labels with DNS/email readiness blocked. |
| Legal/business | Question-only packet with qualified-review gating. |
| Product scope | Selected local learning lane with platform non-restriction and pilot/customer claims blocked. |
| Support readiness | Local support and incident-response shape with support service, SLA, onboarding, paid support, and deployment claims blocked. |
| Intake/onboarding | Local intake and onboarding shape with forms, waitlists, pilot signups, personal data collection, CRM import, outreach, paid access, and customer access blocked. |
| Privacy/data | Local privacy, consent, retention, deletion, processor, and tracking questions with personal-data handling and legal-clearance claims blocked. |
| Public claim alignment | Public-copy and naming checks remain foundation-stage. |
| Governance preflight | Preflight command list, receipt schema, receipt example, and tests. |

## Required Pre-Commit Evidence

Before a future commit request, verify at minimum:

```powershell
python scripts/validate_foundation_mode.py
python scripts/validate_foundation_local_proof_thread.py
python scripts/validate_foundation_private_recovery_boundary.py
python scripts/validate_foundation_secrets_credentials_boundary.py
python scripts/validate_foundation_cost_budget_boundary.py
python scripts/validate_foundation_runtime_environment_boundary.py
python scripts/validate_foundation_backup_export_boundary.py
python scripts/validate_foundation_domain_email_boundary.py
python scripts/validate_foundation_legal_business_boundary.py
python scripts/validate_foundation_product_scope_boundary.py
python scripts/validate_foundation_support_readiness_boundary.py
python scripts/validate_foundation_intake_onboarding_boundary.py
python scripts/validate_foundation_privacy_data_boundary.py
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
