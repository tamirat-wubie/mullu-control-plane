<!--
Purpose: define a local source-control review checklist for Foundation Mode dirty packets without authorizing staging, commit, push, pull request, release, publication, deployment, customer access, legal clearance, company formation, patent action, money movement, or secret publication.
Governance scope: dirty-worktree review questions, runtime-safety packet grouping, unrelated-work separation, untracked-artifact review, validation receipt review, private-value screening, line-ending warning triage, Git-effect stop rules, and next-action gating.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md, examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json, examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json, examples/foundation_validation_receipt_current_packet.awaiting_evidence.json, examples/foundation_next_action_witness.awaiting_evidence.json, examples/foundation_git_effect_stop_rule_current_packet.awaiting_evidence.json, examples/foundation_external_action_stop_rule_current_packet.awaiting_evidence.json, examples/foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.json, examples/foundation_line_ending_warning_current_packet.awaiting_evidence.json, examples/foundation_untracked_artifact_current_packet.awaiting_evidence.json, examples/foundation_unrelated_work_preservation_current_packet.awaiting_evidence.json, examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json, examples/foundation_runtime_safety_current_packet.awaiting_evidence.json, scripts/validate_foundation_source_control_review_checklist_boundary.py.
Invariants: checklist completion blocked, review scope closure blocked, staging blocked, commit blocked, push blocked, pull request blocked, release blocked, external publication blocked, deployment blocked, customer access blocked, legal clearance blocked, company formation blocked, patent action blocked, money movement blocked, and secret publication blocked.
-->

# Foundation Source-Control Review Checklist Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** source-control review checklist preparation means drafting the
> questions a future reviewer should answer before any Git action. It does not
> stage, commit, push, open a pull request, publish, deploy, start customer
> access, make legal or company claims, file patent material, move money, or
> expose secrets.

Witness packet: [`../examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json`](../examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json)

Application packet: [`../examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json`](../examples/foundation_source_control_review_checklist_current_packet.awaiting_evidence.json)

Validation receipt packet: [`../examples/foundation_validation_receipt_current_packet.awaiting_evidence.json`](../examples/foundation_validation_receipt_current_packet.awaiting_evidence.json)

Next-action witness packet: [`../examples/foundation_next_action_witness.awaiting_evidence.json`](../examples/foundation_next_action_witness.awaiting_evidence.json)

Git-effect stop-rule packet: [`../examples/foundation_git_effect_stop_rule_current_packet.awaiting_evidence.json`](../examples/foundation_git_effect_stop_rule_current_packet.awaiting_evidence.json)

External-action stop-rule packet: [`../examples/foundation_external_action_stop_rule_current_packet.awaiting_evidence.json`](../examples/foundation_external_action_stop_rule_current_packet.awaiting_evidence.json)

Dirty-worktree snapshot packet: [`../examples/foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.json`](../examples/foundation_dirty_worktree_snapshot_current_packet.awaiting_evidence.json)

Line-ending warning packet: [`../examples/foundation_line_ending_warning_current_packet.awaiting_evidence.json`](../examples/foundation_line_ending_warning_current_packet.awaiting_evidence.json)

Untracked artifact packet: [`../examples/foundation_untracked_artifact_current_packet.awaiting_evidence.json`](../examples/foundation_untracked_artifact_current_packet.awaiting_evidence.json)

Unrelated work preservation packet: [`../examples/foundation_unrelated_work_preservation_current_packet.awaiting_evidence.json`](../examples/foundation_unrelated_work_preservation_current_packet.awaiting_evidence.json)

Secrets/private-value screening packet: [`../examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json`](../examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json)

Runtime-safety packet: [`../examples/foundation_runtime_safety_current_packet.awaiting_evidence.json`](../examples/foundation_runtime_safety_current_packet.awaiting_evidence.json)

Rule: Source-control review checklist preparation is a local planning boundary,
not checklist completion, review-scope closure, staging approval, commit
approval, push approval, pull-request approval, release readiness, external
publication, deployment readiness, customer access, legal clearance, company
formation, patent action, money movement, or secret publication.

No checklist completion, review-scope closure, staging approval, commit
approval, push approval, pull-request approval, release readiness, external
publication, deployment readiness, customer access, legal clearance, company
formation, patent action, money movement, or secret publication claim is
permitted by this boundary.

## Current State

```text
source_control_review_checklist_state=AwaitingEvidence
checklist_complete_claimed=false
review_scope_closed_claimed=false
validation_complete_claimed=false
secret_clearance_claimed=false
staging_allowed=false
commit_allowed=false
push_allowed=false
pull_request_allowed=false
release_allowed=false
external_publication_allowed=false
deployment_allowed=false
customer_access_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_action_allowed=false
money_action_allowed=false
secret_publication_allowed=false
```

## Checklist Items

| Item | Prepare now | Blocked now |
| --- | --- | --- |
| Dirty worktree snapshot review | Draft how to inspect the changed packet locally. | Do not claim checklist completion. |
| Runtime-safety packet family review | Draft how to group the runtime-safety packet family. | Do not claim review-scope closure. |
| Unrelated or prior work review | Draft how to separate user or prior work. | Do not revert unrelated work. |
| Untracked artifact review | Draft how to inspect validator and test artifacts. | Do not stage untracked files. |
| Validation receipt review | Draft how to review the saved governance receipt. | Do not claim validation completeness. |
| Secret and private value review | Draft how to screen for secret-shaped or private values. | Do not claim secret clearance. |
| Line-ending warning review | Draft how to triage CRLF warning output. | Do not hide warnings. |
| Git-effect stop-rule review | Draft the stop rule for staging, commit, push, and pull request. | Do not authorize Git effects. |
| External-action stop-rule review | Draft the stop rule for customer, legal, company, patent, money, secret, publication, and deployment actions. | Do not authorize external effects. |
| Next-action review | Draft the next bounded local action. | Do not promote to release or deployment. |

## Operator Procedure

1. Keep checklist notes public-safe and local.
2. Refer to categories and verification commands, not private paths, branch
   refs, commit refs, pull request refs, endpoint targets, provider ids,
   customer identifiers, legal conclusions, company filings, patent filings,
   payment details, or secret values.
3. Preserve unrelated work. Do not reset, checkout, delete, move, stage, or
   commit from this boundary.
4. Keep every checklist item in `AwaitingEvidence` until the user explicitly
   requests a source-control action.

## Current Dirty-Packet Application

The current application packet records only public-safe categories:

| Category | Meaning |
| --- | --- |
| Foundation posture and navigation | Central Foundation Mode routes and status docs changed. |
| Dirty-worktree snapshot current-packet triage | Local dirty-worktree presence is recorded without clean-worktree, status-output, count, file-list, ref, ownership, staging, commit, push, or pull request claims. |
| Source-control review checklist boundary | This boundary, witness, current-packet application, validator, and tests changed. |
| Source-control boundary and preflight wiring | Source-control packet and preflight receipt coverage changed. |
| Diff review, change handoff, and test evidence boundaries | Adjacent local review boundaries changed. |
| Unrelated/prior work preservation triage | Local prior or user work possibility is recorded without ownership assignment, file-list closure, reset, checkout, delete, move, revert, staging, commit, push, or pull request claims. |
| Secrets/credentials current-packet screening | Local secret/private-value screening application changed without secret clearance. |
| Line-ending warning current-packet triage | Local LF-to-CRLF warning category is recorded without warning resolution, file-list, Git-config, rewrite, staging, commit, push, or pull request claims. |
| Untracked artifact current-packet triage | Local untracked artifact categories are recorded without artifact closure, counts, path lists, contents, ownership closure, staging, commit, push, or pull request claims. |
| Runtime-safety current-packet triage | Local Phi-GPS v3 runtime-safety packet categories are recorded without runtime-completion, adapter-authority, endpoint, secret-use, full-coverage, Git-effect, publication, or deployment claims. |
| Phi-GPS v3 runtime-safety packet | Local runtime-safety specification and tests changed. |
| Provider, connector, secret, and pagination hardening | Local runtime hardening packet changed. |
| Workspace governance receipt and witness contracts | Local preflight receipt and witness inventory changed. |
| Validation receipt current-packet routing | Local validation receipt packet changed without copying receipt content, counts, timestamps, private paths, or claiming terminal closure. |
| Untracked validator and test artifacts | New local validator and test artifacts exist but remain unstaged. |

It does not record changed-file lists, private values, branch refs, commit refs,
pull request refs, endpoint targets, provider ids, customer identifiers, legal
conclusions, company filings, patent filings, payment details, or secret values.

## Validation Receipt Current-Packet Application

The validation receipt packet records that a saved local preflight receipt is
available as category evidence only. It does not copy receipt content, standard
output, summaries, check counts, failed-check names, generated timestamps,
freshness values, private paths, or terminal closure claims.

Blocked from this packet:

1. receipt content, check output, summary, count, failed-check, timestamp,
   freshness, or private-path recording;
2. full-test pass, complete coverage, CI parity, release readiness, deployment
   readiness, security clearance, secret clearance, customer readiness, legal
   clearance, performance readiness, flake-free, or terminal-closure claims;
3. staging, commit, push, or pull request;
4. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Next-Action Witness Review

The next-action witness records only local continuation triage. It does not
authorize broad continuation execution, external action, deployment,
publication, spending, customer action, legal/business action, claim promotion,
secret use, credential use, service activation, source-control publication,
roadmap commitment, or deadline promise.

Blocked from this witness:

1. broad continuation execution or treating `continue` as permission for many
   tasks;
2. external action, publication, deployment, customer action, legal/business
   action, spending, service activation, credential use, or secret use;
3. source-control publication, staging, commit, push, or pull request approval;
4. roadmap commitment, deadline promise, or claim promotion.

## Git-Effect Stop-Rule Application

The Git-effect stop-rule packet records only source-control effect categories.
It does not approve staging, commit, push, pull request, branch switch, tag
creation, release, source-control publication, status-output publication,
changed-file list closure, exact-diff publication, private-path recording, Git
configuration changes, reset, checkout, or revert.

Blocked from this packet:

1. staging, commit, push, pull request, branch switch, tag creation, release,
   or source-control publication;
2. branch ref, commit ref, pull request ref, status output, changed-file list,
   exact diff, or private-path recording;
3. Git configuration changes;
4. reset, checkout, or revert approval.

## External-Action Stop-Rule Application

The external-action stop-rule packet records only outward-effect categories. It
does not approve customer action, legal action, company action, patent action,
money movement, payment action, secret publication, external publication,
deployment, external account activation, service activation, provider binding,
endpoint target recording, or personal-data collection.

Blocked from this packet:

1. customer access, customer action, or customer identifier recording;
2. legal clearance, legal action, legal conclusion recording, company
   formation, company action, company filing recording, patent action, or
   patent filing recording;
3. money movement, payment action, or payment detail recording;
4. secret publication or secret value recording;
5. external publication, deployment readiness, deployment, external account
   activation, service activation, provider binding, provider id recording,
   endpoint target recording, or personal-data collection.

## Dirty-Worktree Snapshot Application

The dirty-worktree snapshot packet records that local dirty state is present as
a category only. It does not record `git status` output, changed-file counts,
changed-file lists, exact diffs, branch refs, commit refs, pull request refs,
private paths, ownership assignment, or clean-worktree claims.

Blocked from this packet:

1. dirty-worktree closure or clean-worktree claims;
2. status output, counts, file lists, exact diffs, or source-control ref
   publication;
3. private path recording or ownership assignment;
4. staging, commit, push, or pull request;
5. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Line-Ending Warning Application

The line-ending warning packet records that LF-to-CRLF warnings are present as a
category only. It does not record exact warning text, warning counts, changed
file lists, private paths, or file contents.

Blocked from this packet:

1. warning resolution or hiding;
2. line-ending normalization;
3. Git configuration changes;
4. file rewrites;
5. staging, commit, push, or pull request;
6. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Untracked Artifact Application

The untracked artifact packet records that untracked document, example,
validator, and test artifact categories are present. It does not record exact
file lists, counts, private paths, artifact contents, ownership closure, or
review-scope closure.

Blocked from this packet:

1. untracked artifact closure;
2. artifact counts, changed-file lists, or path publication;
3. private path recording;
4. artifact content publication;
5. artifact ownership or review-scope closure;
6. staging, commit, push, or pull request;
7. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Unrelated Work Preservation Application

The unrelated work preservation packet records that prior or user work may be
present in the dirty worktree. It does not record exact file lists, exact diffs,
private paths, ownership assignments, diff-scope closure, or review closure.

Blocked from this packet:

1. unrelated-work or prior-work closure;
2. ownership assignment;
3. changed-file list or diff-scope closure;
4. user-change overwrite;
5. reset, checkout, delete, move, or revert approval;
6. staging, commit, push, or pull request;
7. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Secrets/Private-Value Screening Application

The secrets/private-value screening packet records only public-safe screening
categories. It does not record changed-file lists, private values, secret
values, credential values, assigned environment values, private paths, account
identifiers, provider bindings, secret-scan pass claims, secret-clearance
claims, or Git-effect approval.

Blocked from this packet:

1. real secret storage, credential activation, provider account binding, API
   key creation, OAuth app creation, or service account creation;
2. environment-file commit, private-key storage, secret rotation readiness,
   secret-scan pass, or secret-clearance claims;
3. changed-file list recording, private value recording, secret value
   recording, credential value recording, assigned environment value recording,
   private path recording, account identifier recording, or provider binding
   recording;
4. staging, commit, push, or pull request;
5. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Runtime-Safety Packet Application

The runtime-safety packet records that the Phi-GPS v3 runtime-safety family is
visible as local category evidence only. It does not claim runtime completion,
runtime readiness, adapter authority, provider binding, connector use, endpoint
target evidence, secret use, acceptance-test harness completion, full coverage,
review-scope closure, or deployment readiness.

Blocked from this packet:

1. runtime completion, runtime readiness, public readiness, or customer
   readiness claims;
2. adapter authority, provider binding, connector use, endpoint target
   recording, secret use, or secret value recording;
3. acceptance-test harness completion, full coverage, or review-scope closure;
4. changed-file list recording, private value recording, endpoint value
   recording, provider id recording, or secret value recording;
5. staging, commit, push, or pull request;
6. publication, deployment, customer access, legal/company/patent action, money
   movement, or secret publication.

## Validation

Run:

```powershell
python scripts/validate_foundation_source_control_review_checklist_boundary.py
```

The validator checks that the checklist witness:

1. keeps checklist completion, review-scope closure, validation completeness,
   secret clearance, staging, commit, push, pull request, release, publication,
   deployment, customer access, legal clearance, company formation, patent
   action, money movement, and secret publication blocked;
2. keeps every checklist item in `AwaitingEvidence`;
3. rejects private values, source-control values, customer values, endpoint
   values, legal/company/patent/money values, secret values, publication
   values, or deployment values; and
4. verifies the current-packet application remains category-only with Git,
   publication, deployment, customer, legal, company, patent, money, and secret
   actions blocked; and
5. verifies the validation-receipt current packet remains category-only without
   receipt content, output, summary, count, failed-check, freshness, private
   path, full-test pass, coverage, CI parity, release, deployment, security,
   secret-clearance, customer, legal, terminal-closure, staging, commit, push,
   or pull request claims; and
6. verifies the next-action witness remains category-only without broad
   continuation execution, external action, publication, deployment, customer
   action, legal/business action, spending, service activation, credential use,
   secret use, source-control publication, roadmap commitment, deadline promise,
   staging, commit, push, or pull request approval; and
7. verifies the Git-effect stop-rule packet remains category-only without
   source-control approval, staging, commit, push, pull request, branch switch,
   tag, release, source-control publication, status-output publication,
   changed-file list closure, exact-diff publication, private-path recording,
   Git configuration change, reset, checkout, or revert approval; and
8. verifies the external-action stop-rule packet remains category-only without
   customer, legal, company, patent, money, payment, secret-publication,
   external-publication, deployment, external-account, service, provider,
   endpoint, or personal-data actions or value recording; and
9. verifies the dirty-worktree snapshot packet remains category-only without
   clean-worktree claims, status output, counts, file lists, source-control
   refs, ownership assignment, staging, commit, push, or pull request approval;
   and
10. verifies the line-ending warning packet remains category-only without hiding
   warnings, resolving warnings, normalizing line endings, changing Git config,
   rewriting files, or authorizing Git effects; and
11. verifies the untracked artifact packet remains category-only without
   artifact closure, counts, path lists, content publication, ownership closure,
   staging, commit, push, or pull request approval; and
12. verifies the unrelated work preservation packet remains category-only
   without ownership assignment, file-list closure, reset, checkout, delete,
   move, revert, staging, commit, push, or pull request approval; and
13. verifies the secrets/private-value screening packet remains category-only
   without changed-file list recording, private value recording, secret value
   recording, credential value recording, assigned environment value recording,
   private path recording, account identifier recording, provider binding
   recording, secret clearance, secret-scan pass, staging, commit, push, or
   pull request approval; and
14. verifies the runtime-safety packet remains category-only without runtime
   completion, runtime readiness, adapter authority, provider binding,
   connector use, endpoint target recording, secret use, full coverage,
   staging, commit, push, or pull request approval; and
15. rejects completion, approval, readiness, publication, or deployment
   promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare source control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Review local diff safely | [Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md) |
| Handoff changes safely | [Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md) |
| Record validation evidence safely | [Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: checklist completion blocked, review-scope closure blocked, staging blocked, commit blocked, push blocked, pull request blocked, release blocked, publication blocked, deployment blocked, customer access blocked, legal clearance blocked, company formation blocked, patent action blocked, money movement blocked, secret publication blocked
  Open issues: all checklist items, current-packet application items, validation-receipt review items, next-action witness items, Git-effect stop-rule items, external-action stop-rule items, dirty-worktree snapshot items, line-ending warning triage items, untracked artifact review items, unrelated work preservation items, secrets/private-value screening items, and runtime-safety packet items remain AwaitingEvidence until an explicit source-control request
  Next action: run the checklist validator before using the checklist as source-control evidence
