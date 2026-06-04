<!--
Purpose: define the Foundation Mode private recovery rehearsal boundary for public-safe dry-run planning without executing backup, restore, credential, provider, billing, deletion, or deployment actions.
Governance scope: private recovery rehearsal planning, dry-run scope, public-safe checklist evidence, recovery-material exclusion, credential-use blocking, backup/restore execution blocking, provider-access blocking, deletion blocking, billing blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md, docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md, examples/foundation_private_recovery_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_private_recovery_rehearsal_boundary.py.
Invariants: no recovery rehearsal execution claim, no private recovery material recording, no credential use, no secret use, no backup execution, no restore execution, no cloud sync, no external export, no deletion operation, no provider account access, no billing action, no customer-data handling, no personal-data handling, no restore-readiness claim, and no deployment claim.
-->

# Foundation Private Recovery Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** private recovery rehearsal preparation means drafting the
> shape of a future dry run: what would be checked, what evidence would be
> public-safe, what must remain private, and what would stop the action. It does
> not run a recovery rehearsal, record recovery codes, use credentials, use
> secrets, run backups, restore files, sync cloud storage, export data, delete
> anything, access provider accounts, touch billing, handle customer or personal
> data, claim restore readiness, or deploy anything.

Witness packet: [`../examples/foundation_private_recovery_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_private_recovery_rehearsal_witness.awaiting_evidence.json)

Rule: Private recovery rehearsal preparation is a local dry-run planning
boundary, not permission to execute recovery or expose private recovery
material.

No recovery rehearsal execution, private recovery material recording,
credential use, secret use, backup execution, restore execution, cloud sync,
external export, deletion operation, provider account access, billing action,
customer-data handling, personal-data handling, restore-readiness claim, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

The private recovery inventory must stay outside Git, but the project still
needs a safe way to prepare for a future rehearsal. This boundary gives that
work a public-safe shape without touching the private materials.

This is preparation only:

1. Name the categories that a future private rehearsal would check.
2. Keep all private recovery material outside the repository.
3. Keep all backup, restore, provider, billing, deletion, customer-data,
   personal-data, and deployment actions blocked.
4. Record only public-safe evidence questions and stop rules.
5. Leave the result in `AwaitingEvidence` until a future qualified private
   rehearsal is performed outside Git.

## Current State

```text
private_recovery_rehearsal_boundary_state=AwaitingEvidence
recovery_rehearsal_executed=false
private_recovery_material_recording_allowed=false
credential_use_allowed=false
secret_use_allowed=false
backup_execution_allowed=false
restore_execution_allowed=false
cloud_sync_allowed=false
external_export_allowed=false
deletion_operation_allowed=false
provider_account_access_allowed=false
billing_action_allowed=false
customer_data_handling_allowed=false
personal_data_handling_allowed=false
restore_readiness_claimed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Rehearsal scope | Draft what a future private rehearsal would inspect. | Do not execute the rehearsal. |
| Public-safe inventory check | Name categories from the private recovery inventory. | Do not record recovery codes, account IDs, paths, or secrets. |
| Private-material exclusion | Define what must stay outside Git. | Do not copy private recovery material into repository files. |
| Credential-use stop | Define the stop point before credentials are needed. | Do not use credentials or provider sessions. |
| Backup/restore dry-run questions | Draft what backup and restore evidence would be needed later. | Do not run backups, restore files, sync cloud storage, or export data. |
| Failure-mode questions | Draft what failure would mean and how to stop safely. | Do not delete data or mutate external state. |
| Receipt questions | Define what public-safe receipt could be emitted later. | Do not claim restore readiness or terminal closure. |
| Handoff questions | Draft what a future qualified review would need. | Do not claim deployment, support, customer, or billing readiness. |

## Operator Procedure

1. Start from [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md).
2. Check that real recovery material remains outside Git.
3. Use this boundary only to draft rehearsal questions and stop rules.
4. Stop immediately if work requires credentials, provider accounts, backup
   execution, restore execution, deletion, billing, customer data, personal
   data, cloud sync, external export, or deployment.
5. Keep the public witness in `AwaitingEvidence` until a future private
   rehearsal is performed outside this repository.

## Validation

Run:

```powershell
python scripts/validate_foundation_private_recovery_rehearsal_boundary.py
```

The validator checks that the rehearsal witness:

1. keeps recovery rehearsal execution, private recovery material recording,
   credential use, secret use, backup execution, restore execution, cloud sync,
   external export, deletion, provider account access, billing action,
   customer-data handling, personal-data handling, restore-readiness, and
   deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. rejects URL, email, private path, recovery-code, password, token,
   private-key, provider-account, billing, customer-data, personal-data,
   backup-target, restore-target, deletion-target, and deployment-shaped
   values; and
4. rejects promotion phrases that imply rehearsal execution, restore readiness,
   recovery readiness, provider readiness, billing readiness, customer-data
   handling, personal-data handling, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Prepare backup/export safely | [Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: recovery rehearsal execution blocked, private recovery material recording blocked, credential use blocked, secret use blocked, backup execution blocked, restore execution blocked, cloud sync blocked, external export blocked, deletion blocked, provider account access blocked, billing action blocked, customer-data handling blocked, personal-data handling blocked, restore-readiness claim blocked, deployment blocked
  Open issues: rehearsal-scope evidence, inventory-check evidence, private-material exclusion evidence, credential-stop evidence, backup/restore dry-run evidence, failure-mode evidence, receipt evidence, and handoff evidence remain AwaitingEvidence
  Next action: run the private recovery rehearsal validator before relying on rehearsal planning as evidence
