<!--
Purpose: define the Foundation Mode boundary for preparing issue #330 deployment witness evidence handoff slots without collecting live evidence or promoting deployment status.
Governance scope: issue #330, deployment witness evidence handoff, future receipt slots, DNS proof blocking, endpoint proof blocking, secret-presence blocking, repository variable binding blocking, workflow run blocking, artifact publication blocking, status-approval blocking, operator-approval blocking, evidence-ledger routing, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md, docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md, examples/foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_witness_evidence_handoff_boundary.py.
Invariants: no live evidence receipt, no live URL value, no DNS proof claim, no endpoint proof claim, no secret-presence claim, no repository variable binding, no workflow run claim, no witness artifact publication, no deployment status approval claim, no operator approval claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Witness Evidence Handoff Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment witness evidence handoff means naming the future
> evidence slots that a later external operator thread would need. It does not
> collect live receipts, record live gateway URL values, prove DNS, prove
> endpoints, claim secret presence, bind repository variables, claim workflow
> runs, publish artifacts, approve status, approve operators, open access, move
> money, make legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json`](../examples/foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json)

Rule: Deployment witness evidence handoff is a local list of future evidence
slots. It is not live evidence, not operator approval, not publication, and not
a deployment witness.

No live evidence receipt, live URL value, DNS proof, endpoint proof, secret
presence claim, repository variable binding, workflow run claim, witness
artifact publication, deployment status approval claim, operator approval
claim, customer access, personal-data collection, money movement,
legal-clearance claim, company-formation claim, patent claim, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

After input names and preflight labels are visible, the next failure mode is
treating missing future evidence as if it already exists. This boundary keeps
the handoff structure visible while every evidence slot remains
`AwaitingEvidence`.

Use it when the question is:

1. Which future evidence slots must exist before issue #330 can move?
2. Which slots belong to an external operator thread?
3. Which slots are only local ledger references today?
4. Which approval claims remain blocked?
5. Which evidence must not be copied into Git?

## Current State

```text
deployment_witness_evidence_handoff_state=AwaitingEvidence
live_evidence_receipt_recorded=false
live_gateway_url_value_allowed=false
dns_proof_claimed=false
endpoint_proof_claimed=false
secret_presence_claimed=false
repository_variable_binding_allowed=false
workflow_run_claimed=false
witness_artifact_publication_allowed=false
deployment_status_approval_claimed=false
operator_approval_claimed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Handoff Labels

These are slot labels only. They are not paths to live artifacts, URLs, run
identifiers, secret identifiers, account identifiers, provider identifiers, or
approval records.

| Label | Future role | Boundary |
| --- | --- | --- |
| `deployment_witness_receipt` | Future deployment witness receipt slot. | Do not collect or attach a live receipt. |
| `gateway_publication_readiness_report` | Future gateway publication readiness report slot. | Do not claim report readiness. |
| `deployment_publication_closure_plan` | Future deployment publication closure-plan slot. | Do not claim closure approval. |
| `dns_resolution_receipt` | Future DNS proof slot. | Do not claim DNS proof. |
| `endpoint_probe_receipt` | Future endpoint proof slot. | Do not claim endpoint proof. |
| `runtime_witness_receipt` | Future runtime witness slot. | Do not claim runtime witness pass. |
| `runtime_conformance_receipt` | Future runtime conformance slot. | Do not claim runtime conformance pass. |
| `workflow_run_receipt` | Future workflow run slot. | Do not claim workflow execution. |
| `artifact_publication_receipt` | Future artifact publication slot. | Do not publish or promote artifacts. |
| `deployment_status_approval` | Future status approval slot. | Do not claim status approval. |
| `operator_decision` | Future operator decision slot. | Do not claim operator approval. |

## Handoff Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Deployment witness receipt slot | Record the future evidence slot name. | Do not record live witness receipts. |
| Gateway readiness report slot | Record the future report slot name. | Do not claim readiness report pass. |
| Closure plan receipt slot | Record the future closure-plan slot name. | Do not claim closure approval. |
| DNS resolution receipt slot | Record the future DNS proof slot name. | Do not claim DNS proof. |
| Endpoint probe receipt slot | Record the future endpoint proof slot name. | Do not probe or claim endpoints. |
| Runtime witness receipt slot | Record the future runtime witness slot name. | Do not claim runtime witness pass. |
| Runtime conformance receipt slot | Record the future conformance slot name. | Do not claim conformance pass. |
| Workflow run receipt slot | Record the future workflow run slot name. | Do not dispatch or claim workflow runs. |
| Artifact publication receipt slot | Record the future artifact slot name. | Do not publish or promote artifacts. |
| Deployment status approval slot | Record the future status approval slot name. | Do not approve or promote deployment status. |
| Operator decision slot | Record the future operator decision slot name. | Do not claim operator approval. |
| Evidence ledger entry slot | Record that a later ledger entry is needed. | Do not promote local ledger entries into live evidence. |

## Operator Procedure

1. Treat this boundary as a handoff-slot checklist, not an evidence collector.
2. Keep only public-safe slot labels and blocked-gate labels in Git.
3. Do not place live receipts, real hosts, URLs, provider identifiers, account
   identifiers, repository variable values, secret values, run ids, artifact
   ids, approval ids, personal data, or private paths in this witness.
4. Stop if the next step requires live evidence collection, DNS proof, endpoint
   proof, secret handling, repository variable mutation, workflow dispatch,
   artifact upload, status approval, operator approval, customer access,
   payment, legal/business action, publication, or deployment.
5. Route future evidence through an external operator thread and then into the
   evidence ledger only after a governed promotion gate exists.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_witness_evidence_handoff_boundary.py
```

The validator checks that the deployment witness evidence handoff witness:

1. keeps every handoff slot in `AwaitingEvidence`;
2. keeps live receipts, live gateway URL values, DNS proof, endpoint proof,
   secret presence, repository variable binding, workflow runs, artifact
   publication, status approval, operator approval, customer access, money,
   legal/business claims, publication, and deployment blocked;
3. allows only public-safe handoff labels and local slot notes;
4. rejects live URLs, private paths, email-like identifiers, assignment shapes
   for secrets, accounts, providers, approvals, receipts, reports, artifacts,
   customers, money, legal/business facts, and deployment facts; and
5. rejects evidence, approval, publication, status, and deployment promotion
   phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Inventory deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Record local evidence references | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: live evidence not recorded, DNS proof not claimed, endpoint proof not claimed, secret presence not claimed, repository variable binding blocked, workflow run claim blocked, artifact publication blocked, status approval not claimed, operator approval not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all deployment witness evidence handoff slots remain AwaitingEvidence
  Next action: validate this handoff boundary before any future deployment witness evidence collection or promotion work
