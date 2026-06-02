<!--
Purpose: define the Foundation Mode operations/runbook boundary before any runbook-execution, incident-response, monitoring, on-call, SLO, recovery-readiness, customer-support-operations, external-publication, or deployment claim.
Governance scope: runbook-inventory questions, procedure-dry-run questions, incident-response questions, monitoring/alert questions, on-call/escalation questions, SLO/error-budget questions, rollback/recovery questions, operational-graph questions, MIL-audit-runbook questions, evidence-promotion questions, customer-support blocking, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md, docs/19_skill_system.md, docs/31_operational_graph.md, docs/64_mil_audit_runbook_workflow.md, examples/foundation_operations_runbook_witness.awaiting_evidence.json, scripts/validate_foundation_operations_runbook_boundary.py.
Invariants: no runbook execution claim, no incident-response readiness claim, no monitoring readiness claim, no alerting readiness claim, no on-call readiness claim, no SLO or error-budget claim, no recovery readiness claim, no operational-graph completeness claim, no MIL runbook admission readiness claim, no customer-support operations, no external publication, and no deployment claim.
-->

# Foundation Operations Runbook Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future operators -->

> **In one box:** operations/runbook preparation means drafting local procedure
> questions so future work can become repeatable, observable, and recoverable.
> It does not mean runbooks are executable, incidents are covered, monitoring is
> live, on-call exists, SLOs are active, recovery is ready, customer support is
> open, or deployment is approved.

Witness packet: [`../examples/foundation_operations_runbook_witness.awaiting_evidence.json`](../examples/foundation_operations_runbook_witness.awaiting_evidence.json)

Rule: Operations/runbook preparation is a local planning boundary, not a runbook-execution, incident-response, monitoring, on-call, SLO, recovery-readiness, customer-support, publication, or deployment certificate.

No runbook execution, incident-response readiness, monitoring readiness,
alerting readiness, on-call readiness, SLO or error-budget claim, recovery
readiness, operational-graph completeness, MIL runbook admission readiness,
customer-support operations, external publication, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

The repository already contains runbook and operational graph architecture. In
Foundation Mode, those docs must stay as local preparation until one exact
operational claim has witness evidence.

This boundary separates preparation from proof:

1. Procedures can be named without claiming they are executable runbooks.
2. Incident, monitoring, alerting, and on-call questions can be drafted without
   claiming operational readiness.
3. SLO, recovery, rollback, and operational graph questions can be prepared
   without claiming live service obligations.
4. MIL-audit runbook workflow references can stay local until store paths,
   replay, learning admission, and runbook storage evidence are signed.
5. Future customer-support or deployment operations remain blocked until later
   evidence promotes one exact action.

## Current State

```text
operations_runbook_boundary_state=AwaitingEvidence
operations_runbook_claimed=false
runbook_execution_allowed=false
incident_response_ready=false
monitoring_ready=false
alerting_ready=false
on_call_ready=false
slo_claimed=false
recovery_ready=false
operational_graph_complete=false
mil_runbook_admission_ready=false
customer_support_operations_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Preparation Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Runbook-inventory questions | List local procedures that may need runbooks later. | Do not claim executable runbooks or trusted skills. |
| Procedure-dry-run questions | Draft inputs, outputs, stop rules, and receipts. | Do not execute operations or mutate runtime state. |
| Incident-response questions | Draft severity, containment, and escalation questions. | Do not claim incident coverage or response readiness. |
| Monitoring/alert questions | Draft signal, alert, and dashboard questions. | Do not claim live monitoring or alerting. |
| On-call/escalation questions | Draft handoff and escalation paths. | Do not claim staffed on-call or support coverage. |
| SLO/error-budget questions | Draft protected variables and thresholds. | Do not claim SLOs, error budgets, or production obligations. |
| Rollback/recovery questions | Draft rollback, compensation, and recovery evidence needs. | Do not claim recovery readiness. |
| Operational-graph questions | Draft node and edge evidence references. | Do not claim graph completeness or live operational truth. |
| MIL-audit-runbook questions | Draft hash-chain, replay, and admission prerequisites. | Do not claim runbook admission readiness. |
| Evidence-promotion questions | Draft what a later witness must prove. | Do not publish, open customer support, or deploy. |

## Operator Procedure

1. Keep operations/runbook preparation as local questions unless a later signed
   witness promotes one exact operational step.
2. Do not store private store paths, service URLs, personal contact details,
   alert destinations, provider account ids, secrets, or customer information
   in the witness.
3. Treat any runbook execution, incident response, monitoring, alerting,
   on-call, SLO, recovery, customer-support, publication, or deployment
   conclusion as `AwaitingEvidence`.
4. If a future task needs real operational execution, create a separate witness
   for the exact action before running a procedure, opening support, publishing
   operational claims, or deploying.

## Validation

Run:

```powershell
python scripts/validate_foundation_operations_runbook_boundary.py
```

The validator checks that the operations/runbook witness:

1. keeps every preparation surface in `AwaitingEvidence`;
2. keeps runbook execution, incident response, monitoring, alerting, on-call,
   SLO, recovery, operational graph, MIL runbook admission, customer-support,
   publication, and deployment claims blocked;
3. rejects URL, email, private path, alert destination, account, secret,
   customer, or provider-shaped values; and
4. rejects promotion phrases that turn local operations questions into
   readiness proof.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Understand skills and runbook promotion | [Skill System](19_skill_system.md) |
| Understand the operational graph | [Operational Graph](31_operational_graph.md) |
| Review MIL audit runbook mechanics | [MIL Audit Runbook Workflow](64_mil_audit_runbook_workflow.md) |
| Keep source control bounded | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: runbook execution blocked, incident-response readiness not claimed, monitoring readiness not claimed, alerting readiness not claimed, on-call readiness not claimed, SLO claims blocked, recovery readiness not claimed, operational-graph completeness not claimed, MIL runbook admission readiness not claimed, customer-support operations blocked, publication blocked, deployment blocked
  Open issues: runbook-inventory evidence, procedure-dry-run evidence, incident-response evidence, monitoring/alert evidence, on-call/escalation evidence, SLO/error-budget evidence, rollback/recovery evidence, operational-graph evidence, MIL-audit-runbook evidence, and evidence-promotion evidence remain AwaitingEvidence
  Next action: run the operations/runbook boundary validator before any future runbook, incident, monitoring, on-call, recovery, customer-support, publication, or deployment claim
