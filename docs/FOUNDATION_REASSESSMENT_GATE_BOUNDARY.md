<!--
Purpose: define the Foundation Mode reassessment gate for deciding whether deployment or pilot prerequisites should remain deferred, using local public-safe questions only.
Governance scope: local reassessment, deployment-start blocking, pilot-start blocking, evidence-promotion blocking, external-action blocking, customer/data blocking, legal/business restraint, money blocking, secret exclusion, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md, examples/foundation_reassessment_gate_witness.awaiting_evidence.json, scripts/validate_foundation_reassessment_gate_boundary.py.
Invariants: no reassessment approval, no prerequisite promotion, no deployment start, no pilot start, no external action, no customer access, no personal-data collection, no legal-clearance claim, no company-formation claim, no patent claim, no money movement, no secret material, no external publication, and no deployment claim.
-->

# Foundation Reassessment Gate Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** reassessment means checking whether the next step should
> stay local. It does not approve deployment, start a pilot, promote evidence,
> contact people, collect data, spend money, handle secrets, publish, form a
> company, file anything, or deploy.

Witness packet: [`../examples/foundation_reassessment_gate_witness.awaiting_evidence.json`](../examples/foundation_reassessment_gate_witness.awaiting_evidence.json)

Rule: Reassessment is a local gate, not an approval certificate for deployment,
pilot work, external action, legal/business action, customer access, payment,
publication, or runtime exposure.

No reassessment approval, prerequisite promotion, deployment start, pilot
start, external action, customer access, personal-data collection,
legal-clearance claim, company-formation claim, patent claim, money movement,
secret material, external publication, or deployment claim is permitted by this
boundary.

## What This Boundary Solves

After many prerequisite surfaces are visible, the next risk is treating
visibility as permission. This gate keeps the operator from turning a list of
questions into an action plan too early. The only allowed output is another
local, reversible, public-safe prerequisite choice.

Use it when the question is:

1. Should deployment prerequisites remain deferred?
2. Should pilot prerequisites remain deferred?
3. Which evidence gap is still hard?
4. Is the operator still within a solo, no-money, no-customer, no-legal-claim
   preparation posture?
5. What is the next smallest local prerequisite that does not cross an
   external boundary?

## Current State

```text
reassessment_gate_state=AwaitingEvidence
reassessment_approved=false
prerequisite_promotion_allowed=false
deployment_start_allowed=false
pilot_start_allowed=false
external_action_allowed=false
customer_access_allowed=false
personal_data_collection_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
money_movement_allowed=false
secret_material_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Reassessment Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Deployment start question | Ask whether deployment should remain deferred. | Do not approve deployment prerequisites or runtime exposure. |
| Pilot start question | Ask whether pilot work should remain deferred. | Do not approve pilot prerequisites, invite participants, or open access. |
| Evidence gap review | List missing local evidence categories. | Do not promote evidence or claim closure. |
| Operator capacity check | Recheck solo capacity and pacing constraints. | Do not claim schedule, team, support, or incident coverage. |
| Risk stop rule | Draft why the next action must stay reversible. | Do not authorize irreversible external action. |
| External boundary check | Recheck DNS, runtime, account, and provider exposure. | Do not mutate DNS, bind providers, dispatch workflows, or activate services. |
| Legal/business stop rule | Recheck qualified-review gaps. | Do not claim legal clearance, company formation, filings, or patent protection. |
| Money/secret stop rule | Recheck payment, cost, and credential blockers. | Do not spend, bind payment methods, move money, or store secrets. |
| Customer/data stop rule | Recheck privacy and access blockers. | Do not collect personal data, invite customers, or open intake. |
| Rollback/recovery check | Recheck rollback and recovery gaps. | Do not claim recovery, incident, or restore readiness. |
| Next local prerequisite selection | Pick one local evidence item. | Do not create roadmap commitments, deadlines, or broad execution. |
| Non-promotion handoff | Record why the result remains `AwaitingEvidence`. | Do not convert reassessment into approval. |

## Operator Procedure

1. Treat reassessment as a pause-and-check gate, not a go signal.
2. Keep all answers local, public-safe, and non-private.
3. Select only one next local prerequisite when evidence is still missing.
4. Stop if the next action requires customers, participants, public routes,
   outside accounts, DNS, runtime exposure, payment, legal/business action,
   private data, secrets, or deployment.
5. Leave deployment and pilot surfaces in `AwaitingEvidence` until a later
   governed witness proves one exact bounded step.

## Validation

Run:

```powershell
python scripts/validate_foundation_reassessment_gate_boundary.py
```

The validator checks that the reassessment witness:

1. keeps reassessment approval, prerequisite promotion, deployment start, pilot
   start, external action, customer access, personal-data collection, legal
   clearance, company formation, patent claim, money movement, secret material,
   external publication, and deployment blocked;
2. keeps every reassessment surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. rejects URL, email, private path, person/customer/provider/account,
   schedule, legal, payment, billing, credential, secret, private-key, and
   deployment-shaped values; and
5. rejects promotion phrases that imply approval, deployment, pilot, customer,
   legal, company, patent, money, publication, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |
| Keep pilot deferred | [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md) |
| Rehearse pilot deferral safely | [Foundation Pilot Deferral Rehearsal Boundary](FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md) |
| Choose one local action | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: reassessment approval blocked, prerequisite promotion blocked, deployment start blocked, pilot start blocked, external action blocked, customer access blocked, personal-data collection blocked, legal-clearance claim blocked, company-formation claim blocked, patent claim blocked, money movement blocked, secret material blocked, external publication blocked, deployment blocked
  Open issues: deployment-start question evidence, pilot-start question evidence, evidence-gap review, operator-capacity evidence, risk-stop evidence, external-boundary evidence, legal/business stop-rule evidence, money/secret stop-rule evidence, customer/data stop-rule evidence, rollback/recovery evidence, next-local-prerequisite evidence, and non-promotion handoff remain AwaitingEvidence
  Next action: run the reassessment gate validator before using reassessment as a local next-step filter
