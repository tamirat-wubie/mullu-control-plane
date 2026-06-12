<!--
Purpose: define the Foundation Mode boundary for rehearsing one local release packet without tag creation, release publication, artifact publication, deployment, customer, legal, company, patent, money, or secret claims.
Governance scope: local release-packet rehearsal, change-family labels, evidence-reference labels, validator-summary labels, test-summary labels, diff-hygiene labels, risk and rollback labels, public-claim review labels, version-label questions, operator review gates, stop-rule rehearsal, private-value exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, docs/FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md, docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md, examples/foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_local_release_packet_rehearsal_boundary.py.
Invariants: no release-packet publication, no release-readiness claim, no tag creation, no GitHub release creation, no changelog publication, no artifact publication, no source-control publication, no external publication, no deployment, no customer access, no legal clearance, no company formation, no patent action, no money movement, no secret publication, and no private-value recording.
-->

# Foundation Local Release Packet Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** local release-packet rehearsal means drafting the labels that
> a future release review would need. It does not create a tag, publish release
> notes, upload artifacts, open customer access, make legal or company claims,
> file patent material, move money, expose secrets, or deploy.

Witness packet: [`../examples/foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json)

Rule: Local release-packet rehearsal is a private Foundation Mode planning
packet, not a release, release-readiness certificate, source-control
publication, deployment witness, customer-access approval, legal clearance,
company action, patent action, money action, or secret-publication event.

No release-packet publication, release-readiness claim, tag creation, GitHub
release creation, changelog publication, artifact publication, source-control
publication, external publication, deployment, customer access, legal
clearance, company formation, patent action, money movement, secret
publication, or private-value recording is permitted by this boundary.

## What This Boundary Solves

Foundation Mode already has local validation and source-control safety
boundaries. A future release will still need a packet that says what changed,
what evidence exists, what risks remain, and which claims stay blocked. This
boundary rehearses that packet without creating a release.

This is preparation only:

1. A future release review shape can be drafted without creating a tag.
2. Evidence references can be named without copying private paths, refs,
   receipts, endpoint values, or secret values.
3. Validation and test summaries can be rehearsed without claiming complete
   coverage, CI parity, or release readiness.
4. Public-claim and rollback questions can be reviewed before any publication.

## Current State

```text
local_release_packet_rehearsal_boundary_state=AwaitingEvidence
release_packet_published=false
release_readiness_claimed=false
version_label_selected=false
tag_creation_allowed=false
github_release_allowed=false
changelog_publication_allowed=false
artifact_publication_allowed=false
source_control_publication_allowed=false
external_publication_allowed=false
deployment_allowed=false
customer_access_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_action_allowed=false
money_movement_allowed=false
secret_publication_allowed=false
private_value_recording_allowed=false
```

## Rehearsal Labels

These labels are stop-rule gates only. They are not release notes, release
artifacts, Git tags, GitHub release records, source-control receipts,
deployment witnesses, customer records, legal records, company records, patent
records, payment records, private paths, endpoint records, or secrets.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `change_family_inventory_rehearsal` | Future change-family inventory proof. | Do not claim release scope closure. |
| `evidence_reference_bundle_rehearsal` | Future evidence-reference bundle proof. | Do not copy receipt contents, private paths, refs, or artifacts. |
| `validator_result_summary_rehearsal` | Future validator-summary proof. | Do not claim full preflight closure or CI parity. |
| `test_result_summary_rehearsal` | Future test-summary proof. | Do not claim complete coverage or flake-free status. |
| `diff_hygiene_summary_rehearsal` | Future diff-hygiene proof. | Do not stage, commit, push, tag, or publish. |
| `risk_and_rollback_note_rehearsal` | Future rollback-note proof. | Do not approve rollback execution or release execution. |
| `public_claim_review_rehearsal` | Future public-claim review proof. | Do not approve public claims or customer access. |
| `version_label_rehearsal` | Future version-label proof. | Do not select a real version, tag, or release id. |
| `operator_review_gate_rehearsal` | Future operator-review proof. | Do not claim approval or readiness. |
| `stop_rule_rehearsal` | Future stop-rule proof. | Do not approve publication, deployment, money movement, legal/company action, patent action, customer access, source control, or secret handling. |

## Operator Procedure

1. Keep the packet local and public-safe.
2. Use change-family labels, not changed-file lists, branch refs, commit refs,
   tag values, pull request refs, release ids, artifact paths, endpoint values,
   customer identifiers, account identifiers, payment details, legal
   conclusions, company records, patent material, or secret values.
3. Summarize validation categories without copying full receipt content or
   claiming terminal release closure.
4. Record public-claim questions before any public wording changes.
5. Stop if the next action needs staging, commit, push, tag creation, GitHub
   release creation, artifact upload, deployment, customer access, legal or
   company action, patent action, money movement, account activation, endpoint
   binding, or secret handling.

## Validation

Run:

```powershell
python scripts/validate_foundation_local_release_packet_rehearsal_boundary.py
```

The validator checks that the local release-packet rehearsal witness:

1. keeps every rehearsal label in `AwaitingEvidence`;
2. keeps release publication, release readiness, tag creation, GitHub release,
   changelog publication, artifact publication, source-control publication,
   external publication, deployment, customer access, legal clearance, company
   formation, patent action, money movement, secret publication, and
   private-value recording blocked;
3. rejects URLs, emails, private paths, branch refs, commit refs, tag values,
   release ids, artifact paths, endpoint values, account values, customer
   values, payment values, legal/company/patent values, and secrets; and
4. rejects promotion phrases that imply release readiness, publication,
   approval, deployment, customer access, legal clearance, company formation,
   patent action, money movement, or secret clearance.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Review source-control effects first | [Foundation Source-Control Review Checklist Boundary](FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md) |
| Verify evidence categories safely | [Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md) |
| Record rollback questions safely | [Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md) |
| Pick one next local action | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: release-packet publication blocked, release-readiness claim blocked, tag creation blocked, GitHub release creation blocked, changelog publication blocked, artifact publication blocked, source-control publication blocked, external publication blocked, deployment blocked, customer access blocked, legal/company/patent claims blocked, money movement blocked, secret publication blocked, private-value recording blocked
  Open issues: all local release-packet rehearsal labels remain AwaitingEvidence
  Next action: run the local release-packet rehearsal validator before treating any release packet as readiness or publication evidence
