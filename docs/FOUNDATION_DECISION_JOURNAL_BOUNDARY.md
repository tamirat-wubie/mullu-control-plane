<!--
Purpose: define the Foundation Mode decision-journal boundary before any decision-execution, irreversible-action, roadmap-commitment, deadline-promise, authority-delegation, customer-commitment, legal-authority, company-action, patent-filing, spending, external-publication, or deployment claim.
Governance scope: decision context, assumption snapshot, option set, constraint check, evidence references, risk stop rule, review cadence, next-action selection, private-value exclusion, and external-commitment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md, examples/foundation_decision_journal_witness.awaiting_evidence.json, examples/foundation_decision_review_cadence.awaiting_evidence.json, scripts/validate_foundation_decision_journal_boundary.py.
Invariants: no decision-execution claim, no irreversible-action claim, no roadmap-commitment claim, no deadline-promise claim, no authority-delegation claim, no customer-commitment claim, no legal-authority claim, no company-action claim, no patent-filing claim, no spending claim, no external-publication claim, and no deployment claim.
-->

# Foundation Decision Journal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** decision-journal preparation means recording local decision
> context, assumptions, options, constraints, evidence references, stop rules,
> review cadence, and next-action selection. It does not execute decisions,
> create irreversible actions, promise deadlines, delegate authority, commit to a
> roadmap, make customer commitments, create legal authority, form a company,
> file a patent, spend money, publish externally, or deploy.

Witness packet: [`../examples/foundation_decision_journal_witness.awaiting_evidence.json`](../examples/foundation_decision_journal_witness.awaiting_evidence.json)

Review-cadence packet: [`../examples/foundation_decision_review_cadence.awaiting_evidence.json`](../examples/foundation_decision_review_cadence.awaiting_evidence.json)

Rule: Decision-journal preparation is a local planning boundary, not a decision-execution, commitment, authority, legal, company, patent, spending, publication, or deployment certificate.

No decision execution, irreversible action, roadmap commitment, deadline
promise, authority delegation, customer commitment, legal authority, company
action, patent filing, spending, external publication, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

Foundation Mode creates many small choices. For a solo operator, the risk is not
only technical complexity; it is losing the reason for a choice, confusing a
draft next action with a promise, or converting a local plan into an external
commitment.

This boundary keeps decision journaling narrow:

1. Decision context can be recorded locally.
2. Assumptions can be separated from evidence.
3. Options can be listed without committing to one.
4. Constraints can be checked before any action.
5. Evidence references can point to local public-safe artifacts.
6. Stop rules and review cadence can stay private-safe and non-binding.
7. Next actions can stay reversible and `AwaitingEvidence`.

## Current State

```text
decision_journal_boundary_state=AwaitingEvidence
decision_review_cadence_state=AwaitingEvidence
decision_execution_allowed=false
irreversible_action_allowed=false
roadmap_commitment_claimed=false
deadline_promise_claimed=false
authority_delegation_claimed=false
customer_commitment_claimed=false
legal_authority_claimed=false
company_action_allowed=false
patent_filing_allowed=false
spending_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Decision Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Decision context | State the local question and why it matters. | Do not execute the decision from the journal. |
| Assumption snapshot | List assumptions and unknowns. | Do not treat assumptions as evidence. |
| Option set | List possible local options. | Do not make a roadmap commitment. |
| Constraint check | Name hard blockers and soft preferences. | Do not bypass deployment, money, legal, customer, or secret blockers. |
| Evidence references | Point to public-safe local artifacts. | Do not record private paths, secrets, customers, providers, or reviewer identities. |
| Risk stop rule | Name when to pause or rollback. | Do not claim incident readiness or operational coverage. |
| Review cadence | Draft a non-binding review rhythm. | Do not promise deadlines, support cadence, or delivery dates. |
| Next-action selection | Pick the next reversible local action. | Do not stage, commit, publish, spend, file, invite, or deploy. |

## Operator Procedure

1. Use the journal to slow decisions down, not to authorize effects.
2. Keep assumptions, evidence, options, constraints, risks, and next actions
   separate.
3. Do not record private schedule, private health, private account, customer,
   provider, reviewer, credential, or secret details in the public witness.
4. Keep every decision surface in `AwaitingEvidence` until a later signed
   witness promotes one exact decision.
5. Treat every next action as reversible unless the user explicitly requests a
   governed irreversible action and the required evidence exists.

## Sample Review Cadence

| Cadence item | Re-check locally | Blocked now |
| --- | --- | --- |
| Context recheck | Re-read the local decision context before choosing a next action. | Do not execute the decision. |
| Assumption recheck | Separate assumptions from evidence. | Do not treat assumptions as proof. |
| Constraint recheck | Re-check deployment, money, legal, customer, publication, secret, and external-boundary blockers. | Do not bypass blockers. |
| Evidence recheck | Point only to public-safe local artifacts. | Do not record private paths, accounts, customers, providers, reviewers, or secrets. |
| Stop-rule recheck | Pause when the next action is broad, irreversible, external, money-related, legal, customer-facing, publication-facing, or deployment-facing. | Do not authorize irreversible action. |
| Next-action recheck | Choose one reversible local next action. | Do not promise a roadmap, delivery date, support rhythm, or external commitment. |

## Validation

Run:

```powershell
python scripts/validate_foundation_decision_journal_boundary.py
```

The validator checks that the decision-journal witness:

1. keeps every decision surface in `AwaitingEvidence`;
2. keeps decision execution, irreversible action, roadmap commitment, deadline
   promise, authority delegation, customer commitment, legal authority, company
   action, patent filing, spending, external publication, and deployment
   blocked;
3. validates the review-cadence packet as `AwaitingEvidence`;
4. rejects URL, email, private path, private schedule, provider, account,
   customer, reviewer, deadline, or secret-shaped values; and
5. rejects decision-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Organize evidence references safely | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: decision execution blocked, irreversible action blocked, roadmap commitment not claimed, deadline promise not claimed, authority delegation not claimed, customer commitment not claimed, legal authority not claimed, company action blocked, patent filing blocked, spending blocked, external publication blocked, deployment blocked
  Open issues: decision context evidence, assumption snapshot evidence, option set evidence, constraint check evidence, evidence-reference evidence, stop-rule evidence, review-cadence evidence, and next-action evidence remain AwaitingEvidence
  Next action: run the decision-journal boundary validator before any future decision-execution or commitment claim
