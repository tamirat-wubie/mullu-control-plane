<!--
Purpose: define the Foundation Mode boundary for routing future issue #330 deployment witness evidence slots into the local evidence ledger without appending live evidence or promoting readiness.
Governance scope: issue #330, deployment witness evidence ledger routing, local route labels, evidence-ledger append blocking, live evidence reference blocking, ledger promotion blocking, terminal-closure blocking, status-approval blocking, operator-approval blocking, external publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md, examples/foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_witness_evidence_ledger_routing_boundary.py.
Invariants: no evidence-ledger append, no live evidence reference, no ledger promotion, no terminal-closure claim, no readiness claim, no DNS proof claim, no endpoint proof claim, no secret-presence claim, no workflow run claim, no artifact publication, no deployment status approval claim, no operator approval claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Witness Evidence Ledger Routing Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment witness evidence ledger routing means naming how
> future issue #330 evidence slots would be routed into a later ledger entry. It
> does not append evidence, record live references, promote readiness, claim
> terminal closure, approve status, approve operators, publish artifacts, open
> access, move money, make legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json`](../examples/foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json)

Rule: Deployment witness evidence ledger routing is a local route map of future
ledger slots. It is not evidence-ledger append, not live evidence reference,
not readiness promotion, not terminal closure, and not a deployment witness.

No evidence-ledger append, live evidence reference, ledger promotion, terminal
closure claim, readiness claim, DNS proof, endpoint proof, secret-presence
claim, workflow run claim, artifact publication, deployment status approval
claim, operator approval claim, customer access, personal-data collection,
money movement, legal-clearance claim, company-formation claim, patent claim,
external publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The evidence handoff boundary names future evidence slots. This routing
boundary names where those slots would later appear in the local evidence
ledger, without creating the ledger entries now.

Use it when the question is:

1. Which future evidence slots will need ledger routes?
2. Which route labels can be stored publicly?
3. Which route still waits for live evidence?
4. Which route requires a later reassessment gate?
5. Which route must not become a readiness or deployment claim?

## Current State

```text
deployment_witness_evidence_ledger_routing_state=AwaitingEvidence
evidence_ledger_append_allowed=false
live_evidence_reference_allowed=false
ledger_promotion_allowed=false
terminal_closure_claimed=false
readiness_claimed=false
dns_proof_claimed=false
endpoint_proof_claimed=false
secret_presence_claimed=false
workflow_run_claimed=false
artifact_publication_allowed=false
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

## Public-Safe Route Labels

These are route labels only. They are not live artifact references, URLs,
receipt identifiers, run identifiers, secret identifiers, provider identifiers,
account identifiers, approval identifiers, or ledger entries.

| Label | Future route | Boundary |
| --- | --- | --- |
| `deployment_witness_receipt_to_evidence_ledger_entry` | Deployment witness receipt slot to ledger entry. | Do not append live evidence. |
| `gateway_readiness_report_to_evidence_ledger_entry` | Gateway readiness report slot to ledger entry. | Do not claim readiness. |
| `closure_plan_receipt_to_evidence_ledger_entry` | Closure-plan receipt slot to ledger entry. | Do not claim closure. |
| `dns_resolution_receipt_to_evidence_ledger_entry` | DNS resolution receipt slot to ledger entry. | Do not claim DNS proof. |
| `endpoint_probe_receipt_to_evidence_ledger_entry` | Endpoint probe receipt slot to ledger entry. | Do not claim endpoint proof. |
| `runtime_witness_receipt_to_evidence_ledger_entry` | Runtime witness receipt slot to ledger entry. | Do not claim runtime witness pass. |
| `runtime_conformance_receipt_to_evidence_ledger_entry` | Runtime conformance receipt slot to ledger entry. | Do not claim conformance pass. |
| `workflow_run_receipt_to_evidence_ledger_entry` | Workflow run receipt slot to ledger entry. | Do not claim workflow execution. |
| `artifact_publication_receipt_to_evidence_ledger_entry` | Artifact publication receipt slot to ledger entry. | Do not publish or promote artifacts. |
| `deployment_status_approval_to_evidence_ledger_entry` | Status approval slot to ledger entry. | Do not claim status approval. |
| `operator_decision_to_evidence_ledger_entry` | Operator decision slot to ledger entry. | Do not claim operator approval. |
| `evidence_ledger_reassessment_gate` | Later reassessment gate for route promotion. | Do not approve reassessment. |

## Routing Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Deployment witness receipt route | Record the route label. | Do not append live witness evidence. |
| Gateway readiness report route | Record the route label. | Do not claim readiness report pass. |
| Closure plan receipt route | Record the route label. | Do not claim closure approval. |
| DNS resolution receipt route | Record the route label. | Do not claim DNS proof. |
| Endpoint probe receipt route | Record the route label. | Do not claim endpoint proof. |
| Runtime witness receipt route | Record the route label. | Do not claim runtime witness pass. |
| Runtime conformance receipt route | Record the route label. | Do not claim runtime conformance pass. |
| Workflow run receipt route | Record the route label. | Do not claim workflow execution. |
| Artifact publication receipt route | Record the route label. | Do not publish or promote artifacts. |
| Deployment status approval route | Record the route label. | Do not claim status approval. |
| Operator decision route | Record the route label. | Do not claim operator approval. |
| Reassessment gate route | Record the route label. | Do not approve reassessment or promote the ledger. |

## Operator Procedure

1. Treat this boundary as a route map, not an evidence ledger append.
2. Keep only public-safe route labels and blocked-gate labels in Git.
3. Do not place live references, real hosts, URLs, provider identifiers, account
   identifiers, repository variable values, secret values, run ids, artifact
   ids, receipt ids, approval ids, personal data, or private paths in this
   witness.
4. Stop if the next step requires ledger append, live evidence reference,
   evidence promotion, terminal closure, readiness promotion, DNS proof,
   endpoint proof, secret handling, workflow execution, artifact publication,
   status approval, operator approval, customer access, payment,
   legal/business action, publication, or deployment.
5. Keep the route in `AwaitingEvidence` until an external operator thread,
   evidence-ledger promotion rule, and reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_witness_evidence_ledger_routing_boundary.py
```

The validator checks that the deployment witness evidence ledger routing
witness:

1. keeps every route surface in `AwaitingEvidence`;
2. keeps ledger append, live evidence references, ledger promotion, terminal
   closure, readiness, DNS proof, endpoint proof, secret presence, workflow
   runs, artifact publication, status approval, operator approval, customer
   access, money, legal/business claims, publication, and deployment blocked;
3. allows only public-safe route labels and local route notes;
4. rejects live URLs, private paths, email-like identifiers, assignment shapes
   for secrets, accounts, providers, receipts, approvals, artifacts, customers,
   money, legal/business facts, and deployment facts; and
5. rejects evidence, ledger, closure, readiness, approval, publication, status,
   and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Name evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Record local evidence references | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: ledger append blocked, live evidence reference blocked, ledger promotion blocked, terminal closure not claimed, readiness not claimed, DNS proof not claimed, endpoint proof not claimed, secret presence not claimed, workflow run claim blocked, artifact publication blocked, status approval not claimed, operator approval not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all deployment witness evidence ledger routing slots remain AwaitingEvidence
  Next action: validate this routing boundary before any future evidence ledger append or route-promotion work
