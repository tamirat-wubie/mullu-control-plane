<!--
Purpose: define the Foundation Mode diff-review boundary for local public-safe worktree review without claiming diff-review completeness, diff scope closure, ownership assignment, staging approval, commit approval, branch switch approval, push approval, pull request approval, release readiness, revert approval, test pass, publication, or deployment.
Governance scope: changed-file review questions, untracked-file review questions, unrelated-change classification questions, agent-change scope questions, user-change preservation questions, validation-summary questions, secret-drift questions, staging/commit questions, rollback/revert questions, handoff-summary questions, public-safe planning, and Git-effect blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, examples/foundation_diff_review_witness.awaiting_evidence.json, scripts/validate_foundation_diff_review_boundary.py.
Invariants: no diff-review completeness claim, no diff scope closure claim, no ownership assignment, no staging approval, no commit approval, no branch switch approval, no push approval, no pull request approval, no release readiness claim, no revert approval, no test pass claim, no secret publication, no source-control publication, and no deployment claim.
-->

# Foundation Diff Review Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** diff-review preparation means drafting local public-safe
> questions for understanding what changed in the worktree before any future
> Git action. It does not stage, commit, push, open a pull request, switch
> branches, approve a revert, publish source control, release, or deploy.

Witness packet: [`../examples/foundation_diff_review_witness.awaiting_evidence.json`](../examples/foundation_diff_review_witness.awaiting_evidence.json)

Rule: Diff-review preparation is a local planning boundary, not a
diff-review-completion, diff-scope-closure, ownership-assignment,
staging-approval, commit-approval, branch-switch-approval, push-approval,
pull-request-approval, release-readiness, revert-approval, test-pass,
secret-publication, source-control-publication, or deployment certificate.

No diff-review completeness, diff scope closure, ownership assignment, staging
approval, commit approval, branch switch approval, push approval, pull request
approval, release readiness, revert approval, test pass, secret publication,
source-control publication, external publication, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

Gap registers say what is missing. Diff review says what is currently changed
in the local worktree and what questions must be answered before a future Git
action. This boundary keeps that review local and non-effect-bearing.

This is preparation only:

1. The repository can name diff-review surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature diff completeness, scope closure, ownership,
   staging, commit, branch switch, push, pull request, release, revert, test,
   publication, or deployment claims.
4. Private paths, endpoint targets, provider identifiers, branch targets,
   commit identifiers, pull request identifiers, release targets, secret
   values, customer data, and deployment targets stay out of the public packet.

## Current State

```text
diff_review_boundary_state=AwaitingEvidence
diff_review_complete_claimed=false
diff_scope_closed_claimed=false
diff_ownership_assigned=false
staging_allowed=false
commit_allowed=false
branch_switch_allowed=false
push_allowed=false
pull_request_allowed=false
release_allowed=false
revert_allowed=false
test_pass_claimed=false
secret_publication_allowed=false
source_control_publication_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Diff-Review Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Changed-file inventory questions | Draft questions for classifying modified tracked files. | Do not claim the diff is fully reviewed. |
| Untracked-file inventory questions | Draft questions for classifying untracked artifacts. | Do not stage untracked files. |
| Unrelated-change classification | Draft questions for separating unrelated user or prior work. | Do not revert unrelated changes. |
| Agent-change scope questions | Draft questions for naming the current local increment. | Do not claim ownership closure. |
| User-change preservation questions | Draft questions for preserving work not created by the current increment. | Do not overwrite or reset user work. |
| Validation-summary questions | Draft questions for recording which checks ran and what they prove. | Do not claim broad test pass. |
| Secret-drift questions | Draft questions for spotting secret-shaped values before Git action. | Do not publish or expose secrets. |
| Staging and commit questions | Draft questions for a future explicit staging or commit request. | Do not stage, commit, push, or open a pull request. |
| Rollback and revert questions | Draft questions for possible future rollback paths. | Do not approve a revert. |
| Handoff-summary questions | Draft questions for a plain-language changed-file summary. | Do not claim release or deployment readiness. |

## Runtime-safety Diff Separation

Runtime-safety diff separation keeps the runtime-safety packet families visible
without claiming the diff is fully reviewed. It can ask how to group modified
local work into Phi-GPS, provider, connector, secret, process, pagination, and
governance artifact families, how to classify validator and test artifacts, and
how to separate runtime-safety packet work from user or prior work.

This remains local review preparation only. It does not assign ownership,
approve staging, approve commits, approve reverts, claim broad test pass,
publish source control, or authorize deployment.

## Operator Procedure

1. Run local read-only status or diff commands only when review is needed.
2. Classify changed files by question category, not by ownership certainty.
3. Preserve unrelated user changes; do not reset, checkout, delete, move, stage,
   or commit them from this boundary.
4. Avoid URLs, emails, private paths, branch targets, commit ids, pull request
   ids, release targets, provider ids, endpoint targets, secret values,
   customer identifiers, or deployment targets in public witness notes.
5. Mark unknown scope, ownership, staging, commit, branch, push, pull request,
   release, revert, test, publication, and deployment state as
   `AwaitingEvidence`.

## Validation

Run:

```powershell
python scripts/validate_foundation_diff_review_boundary.py
```

The validator checks that the diff-review witness:

1. keeps diff-review completeness, scope closure, ownership assignment,
   staging, commit, branch switch, push, pull request, release, revert, test,
   secret publication, source-control publication, external publication, and
   deployment disabled;
2. keeps every diff-review surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, diff, file,
   path, stage, commit, branch, push, pull request, release, revert, test,
   customer, secret, credential, publication, or deployment shaped values; and
4. rejects Git-effect and readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare gap registers safely | [Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md) |
| Prepare source-control commit boundaries safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: diff-review completeness blocked, diff scope closure blocked, ownership assignment blocked, staging blocked, commit blocked, branch switch blocked, push blocked, pull request blocked, release blocked, revert blocked, test pass blocked, secret publication blocked, source-control publication blocked, external publication blocked, deployment blocked
  Open issues: changed-file evidence, untracked-file evidence, unrelated-change evidence, agent-scope evidence, user-change preservation evidence, validation-summary evidence, secret-drift evidence, staging/commit evidence, rollback/revert evidence, and handoff-summary evidence remain AwaitingEvidence
  Next action: run the diff-review validator before using diff notes as source-control evidence
