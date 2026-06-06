<!--
Purpose: define the Foundation Mode change-handoff boundary for explaining local worktree changes without claiming review completeness, staging approval, commit approval, publication, or deployment.
Governance scope: change-family summary questions, constructive-delta questions, fracture-delta questions, unrelated-change questions, user-change preservation questions, validation-evidence questions, secret-drift questions, rollback/revert questions, next-action questions, operator-handoff questions, public-safe planning, and Git-effect blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, examples/foundation_change_handoff_witness.awaiting_evidence.json, scripts/validate_foundation_change_handoff_boundary.py.
Invariants: no change-handoff completeness claim, no changed-file review completeness claim, no diff scope closure claim, no ownership assignment, no validation completeness claim, no secret-clearance claim, no staging approval, no commit approval, no branch switch approval, no push approval, no pull request approval, no release readiness claim, no revert approval, no source-control publication, no external publication, and no deployment claim.
-->

# Foundation Change Handoff Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** change-handoff preparation means drafting local public-safe
> questions for explaining what changed, what evidence ran, what remains
> unknown, and what a future reviewer should check. It does not complete review,
> stage, commit, push, open a pull request, approve a revert, publish source
> control, release, or deploy.

Witness packet: [`../examples/foundation_change_handoff_witness.awaiting_evidence.json`](../examples/foundation_change_handoff_witness.awaiting_evidence.json)

Rule: Change-handoff preparation is a local planning boundary, not a
change-handoff-completion, changed-file-review-completion, diff-scope-closure,
ownership-assignment, validation-completeness, secret-clearance,
staging-approval, commit-approval, branch-switch-approval, push-approval,
pull-request-approval, release-readiness, revert-approval,
source-control-publication, external-publication, or deployment certificate.

No change-handoff completeness, changed-file review completeness, diff scope
closure, ownership assignment, validation completeness, secret clearance,
staging approval, commit approval, branch switch approval, push approval, pull
request approval, release readiness, revert approval, source-control
publication, external publication, or deployment claim is permitted by this
boundary.

## Why This Exists

Foundation Mode has many local artifacts. Once the worktree accumulates changes,
a future reviewer needs a simple handoff shape:

1. what changed;
2. why it changed;
3. what checks ran;
4. what still remains `AwaitingEvidence`;
5. what must not be staged, committed, pushed, reverted, published, or deployed
   without explicit instruction.

This boundary prepares that handoff shape without turning it into approval.

## Current State

```text
change_handoff_boundary_state=AwaitingEvidence
change_handoff_complete_claimed=false
changed_file_review_complete_claimed=false
diff_scope_closed_claimed=false
change_ownership_assigned=false
validation_complete_claimed=false
secret_clearance_claimed=false
staging_allowed=false
commit_allowed=false
branch_switch_allowed=false
push_allowed=false
pull_request_allowed=false
release_allowed=false
revert_allowed=false
source_control_publication_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Change-Handoff Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Change-family summary questions | Draft how to group local changes by family. | Do not claim the handoff is complete. |
| Constructive-delta questions | Draft what was added or improved. | Do not claim full changed-file review. |
| Fracture-delta questions | Draft what was removed, blocked, or intentionally deferred. | Do not claim diff scope closure. |
| Unrelated-change questions | Draft how to separate unrelated worktree changes. | Do not claim ownership assignment. |
| User-change preservation questions | Draft how to preserve work not created by this increment. | Do not overwrite or reset user work. |
| Validation-evidence questions | Draft which checks ran and what they prove. | Do not claim validation completeness or broad test pass. |
| Secret-drift questions | Draft how to spot secret-shaped content before a Git action. | Do not claim secret clearance. |
| Rollback/revert questions | Draft future rollback and revert review questions. | Do not approve a revert. |
| Next-action questions | Draft the next bounded local action. | Do not authorize broad continuation. |
| Operator-handoff questions | Draft plain-language reviewer notes. | Do not authorize staging, commit, push, pull request, release, publication, or deployment. |

## Runtime-safety Packet Handoff

Runtime-safety packet handoff keeps the Phi-GPS v3 runtime-safety packet category visible without converting it into review closure. The handoff can ask
how to explain local Phi-GPS, provider, connector, secret, process, and pagination hardening, and how to reference local validators, tests, hygiene scans, and governance receipt checks.

This remains local preparation only. It does not claim changed-file review
completion, validation completeness, secret clearance, publication, or
deployment.

## Operator Procedure

1. Keep the handoff public-safe and local.
2. Name only categories, file families, validators, and outcomes. Do not record
   private paths, secret values, provider ids, endpoint targets, branch targets,
   commit ids, pull request ids, customer identifiers, or deployment targets.
3. Preserve unrelated user work. Do not reset, checkout, delete, move, stage, or
   commit from this boundary.
4. Label unknowns as `AwaitingEvidence`.
5. Treat handoff notes as review input, not as approval for Git or deployment
   effects.

## Validation

Run:

```powershell
python scripts/validate_foundation_change_handoff_boundary.py
```

The validator checks that the change-handoff witness:

1. keeps handoff completeness, review completeness, diff scope closure,
   ownership, validation completeness, secret clearance, staging, commit,
   branch switch, push, pull request, release, revert, publication, and
   deployment disabled;
2. keeps every change-handoff surface in `AwaitingEvidence`;
3. rejects URL, email, private path, source-control, validation, secret,
   customer, publication, or deployment shaped values; and
4. rejects readiness and Git-effect promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Review local changes safely | [Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md) |
| Prepare source control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |

STATUS:
  Completeness: 100%
  Invariants verified: change-handoff completeness blocked, changed-file review completeness blocked, diff scope closure blocked, ownership assignment blocked, validation completeness blocked, secret clearance blocked, staging blocked, commit blocked, branch switch blocked, push blocked, pull request blocked, release blocked, revert blocked, source-control publication blocked, external publication blocked, deployment blocked
  Open issues: change-family evidence, constructive-delta evidence, fracture-delta evidence, unrelated-change evidence, user-change preservation evidence, validation-evidence evidence, secret-drift evidence, rollback/revert evidence, next-action evidence, and operator-handoff evidence remain AwaitingEvidence
  Next action: run the change-handoff validator before using handoff notes as source-control evidence
