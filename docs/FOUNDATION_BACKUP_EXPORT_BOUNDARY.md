<!--
Purpose: define the Foundation Mode backup/export boundary before any repository, evidence, or private-data movement.
Governance scope: local backup planning, export planning, archive planning, redaction planning, restore-drill questions, deletion caution, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_backup_export_witness.awaiting_evidence.json, scripts/validate_foundation_backup_export_boundary.py.
Invariants: no backup execution claim, no cloud backup claim, no external export claim, no public archive claim, no private path in Git, no secret export, no personal-data export, no deletion operation, no restore readiness claim, and no deployment claim.
-->

# Foundation Backup Export Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** backup/export preparation means deciding what should be
> backed up, exported, redacted, archived, or restore-tested later. It does not
> run a backup, activate cloud sync, export files, publish an archive, delete
> data, record private paths, move secrets, move personal data, claim restore
> readiness, or deploy anything.

Witness packet: [`../examples/foundation_backup_export_witness.awaiting_evidence.json`](../examples/foundation_backup_export_witness.awaiting_evidence.json)

Rule: Backup/export preparation is a local planning boundary, not permission to move repository or private data.

No backup execution, cloud backup activation, external export, public archive,
private path recording, secret export, personal-data export, deletion operation,
restore-readiness claim, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Private foundation work needs a future recovery and handoff shape, but the
unsafe move is to start copying material before scope, redaction, retention,
and restore evidence are clear. This document keeps backup/export work at the
question-and-inventory layer.

This is preparation only:

1. The repository can name backup/export surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. The operator can later decide what belongs in a private backup plan.
4. No files, secrets, private paths, personal records, cloud storage, or public
   archives are moved by this document or validator.

## Current State

```text
backup_export_boundary_state=AwaitingEvidence
backup_execution_allowed=false
cloud_backup_allowed=false
external_export_allowed=false
public_archive_allowed=false
private_path_recording_allowed=false
secret_export_allowed=false
personal_data_export_allowed=false
deletion_operation_allowed=false
restore_readiness_claimed=false
deployment_allowed=false
```

## Backup/Export Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Backup inventory draft | List categories that may need protection. | Do not run backup tools or record private target paths. |
| Export scope questions | Decide what future exports would contain. | Do not export repository, evidence, secrets, or private records. |
| Local archive questions | Define what a local archive would preserve. | Do not publish or sync an archive. |
| Restore drill questions | Draft how a future restore would be tested. | Do not claim restore readiness. |
| Redaction checklist | Name what must be removed before sharing. | Do not move secret or personal values. |
| Retention snapshot questions | Draft retention and expiry questions. | Do not approve retention policy or delete evidence. |
| Deletion recovery questions | Describe recovery checks before deletion. | Do not delete repository, evidence, or private records. |
| Handoff bundle questions | Draft a future bundle outline. | Do not publish a bundle or handoff package. |

## Operator Procedure

1. Keep all real private paths, account details, provider IDs, and recovery
   locations outside Git.
2. Record only public-safe categories, questions, and blocked claims.
3. Treat every backup/export surface as `AwaitingEvidence` until a future
   private plan exists.
4. Before any real backup/export action, define scope, redaction, retention,
   restore test, rollback, and deletion safeguards.
5. Do not activate cloud storage, sync clients, public archives, or deployment
   flows from this Foundation Mode boundary.

## Validation

Run:

```powershell
python scripts/validate_foundation_backup_export_boundary.py
```

The validator checks that the backup/export witness:

1. keeps backup execution, cloud backup, external export, public archive,
   private path recording, secret export, personal-data export, deletion,
   restore-readiness, and deployment disabled;
2. keeps every surface in `AwaitingEvidence`;
3. rejects URL, email, private path, secret, archive target, cloud target,
   deletion target, and personal-data shaped values; and
4. rejects readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: backup execution blocked, cloud backup blocked, external export blocked, public archive blocked, private path recording blocked, secret export blocked, personal-data export blocked, deletion blocked, restore-readiness claim blocked, deployment blocked
  Open issues: backup scope, redaction rules, retention rules, restore drill, deletion safeguards, and handoff bundle remain AwaitingEvidence
  Next action: run the backup/export boundary validator before any future private backup/export plan
