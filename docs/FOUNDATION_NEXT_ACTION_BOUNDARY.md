<!--
Purpose: define the Foundation Mode next-action boundary for "continue" work before any external action, commitment, publication, deployment, spending, credential use, or readiness claim.
Governance scope: continuation triage, smallest prerequisite selection, dependency check, local edit scope, verification planning, stop rules, evidence receipts, handoff summaries, public-safe planning, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md, examples/foundation_next_action_witness.awaiting_evidence.json, scripts/validate_foundation_next_action_boundary.py.
Invariants: no broad continuation execution, no external action, no deployment, no publication, no spending, no customer action, no legal/business action, no claim promotion, no secret use, no credential use, no service activation, no source-control publication, no roadmap commitment, and no deadline promise.
-->

# Foundation Next Action Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** next-action preparation means a future `continue` request
> must choose one small local prerequisite, verify it, and stop with evidence.
> It does not authorize broad execution, deployment, publication, spending,
> customer action, legal/business action, claim promotion, secret use,
> credential use, service activation, source-control publication, roadmap
> commitment, or deadline promises.

Witness packet: [`../examples/foundation_next_action_witness.awaiting_evidence.json`](../examples/foundation_next_action_witness.awaiting_evidence.json)

Rule: Next-action preparation is a local continuation boundary, not permission
to execute broad work or cross an external boundary.

No broad continuation execution, external action, deployment, external
publication, spending, customer action, legal/business action, claim promotion,
secret use, credential use, service activation, source-control publication,
roadmap commitment, or deadline promise is permitted by this boundary.

## What This Boundary Solves

Foundation Mode can drift if every `continue` request tries to solve the whole
project. This boundary keeps continuation work atomic:

1. Restate the active objective in local-safe terms.
2. Pick one prerequisite surface that improves the foundation.
3. Check whether the surface depends on deployment, money, legal review,
   customers, secrets, credentials, or publication.
4. If it does, keep it in `AwaitingEvidence` and pick a local-safe subtask.
5. Verify the local subtask with focused checks before any broader claim.

This is preparation only. It does not create a roadmap commitment, delivery
date, product launch, customer promise, legal authority, service activation, or
source-control publication.

## Current State

```text
next_action_boundary_state=AwaitingEvidence
broad_continuation_execution_allowed=false
external_action_allowed=false
deployment_allowed=false
external_publication_allowed=false
spending_allowed=false
customer_action_allowed=false
legal_business_action_allowed=false
claim_promotion_allowed=false
secret_use_allowed=false
credential_use_allowed=false
service_activation_allowed=false
source_control_publication_allowed=false
roadmap_commitment_claimed=false
deadline_promise_claimed=false
```

## Next-Action Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Continue-request triage | Restate what `continue` means for the current local goal. | Do not treat `continue` as permission for broad execution. |
| Smallest prerequisite selection | Pick one local prerequisite row or one bounded repair. | Do not skip to deployment, customers, legal action, or money. |
| Dependency check | Name hard dependencies and `AwaitingEvidence` blockers. | Do not bypass unknown hard constraints. |
| Local edit scope | Keep edits to docs, validators, tests, fixtures, or receipts. | Do not mutate external systems, website files, DNS, accounts, or services. |
| Verification plan | Define focused validators, tests, and preflight evidence. | Do not claim completion from unchecked intent. |
| Stop rule | Stop after one atomic increment and report remaining unknowns. | Do not silently expand scope into roadmap or deadlines. |
| Evidence receipt plan | Save local receipts when governance checks run. | Do not expose secrets, private paths, customer data, or credentials. |
| Handoff summary | Report changed surfaces, checks, and next safe action. | Do not stage, commit, push, publish, or deploy without explicit request. |

## Operator Procedure

1. Start from [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md).
2. Choose one local-safe prerequisite or one local-safe repair.
3. Confirm it does not require deployment, customers, legal action, money,
   secrets, credentials, external publication, or service activation.
4. Add or repair only the smallest useful artifact family.
5. Run focused validators and tests for that family.
6. If governed surfaces changed, run the saved workspace preflight receipt.
7. Report the result as `SolvedVerified`, `SolvedUnverified`, or
   `AwaitingEvidence` with concrete evidence.

## Validation

Run:

```powershell
python scripts/validate_foundation_next_action_boundary.py
```

The validator checks that the next-action witness:

1. keeps broad continuation execution, external action, deployment,
   publication, spending, customer action, legal/business action, claim
   promotion, secret use, credential use, service activation, source-control
   publication, roadmap commitment, and deadline promise blocked;
2. keeps every next-action surface in `AwaitingEvidence`;
3. rejects URL, email, private path, customer, provider, account, secret,
   credential, service, deployment, spending, legal, publication, Git
   publication, roadmap, or deadline shaped values; and
4. rejects promotion phrases that imply continuation authority or readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| Pick a prerequisite row | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Record a decision without executing it | [Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |
| Keep pilot deferred | [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: broad continuation blocked, external action blocked, deployment blocked, publication blocked, spending blocked, customer action blocked, legal/business action blocked, claim promotion blocked, secret use blocked, credential use blocked, service activation blocked, source-control publication blocked, roadmap commitment blocked, deadline promise blocked
  Open issues: continue-request triage evidence, smallest-prerequisite evidence, dependency-check evidence, local-edit-scope evidence, verification-plan evidence, stop-rule evidence, receipt-plan evidence, and handoff-summary evidence remain AwaitingEvidence
  Next action: run the next-action boundary validator before relying on future broad continue requests
