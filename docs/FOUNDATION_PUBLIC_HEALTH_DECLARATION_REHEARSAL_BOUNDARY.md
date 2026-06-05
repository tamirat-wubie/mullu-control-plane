<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 public health declaration receipt fields without declaring public health or mutating deployment status.
Governance scope: issue #330, public health declaration rehearsal, deployment status mutation blocking, declaration receipt blocking, public health endpoint value blocking, operator approval reference blocking, audited-date blocking, schema-validation claim blocking, closure-validation claim blocking, evidence-ledger append blocking, workflow blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md, examples/foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_public_health_declaration_rehearsal_boundary.py.
Invariants: no public health declaration, no deployment status mutation, no declaration receipt writing, no deployment witness publication claim, no public health endpoint value, no operator approval reference value, no audited-date value, no schema-validation pass claim, no closure-validation pass claim, no endpoint-match claim, no evidence-ledger append, no workflow dispatch, no artifact publication, no readiness claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Public Health Declaration Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** public health declaration rehearsal means naming the future
> receipt fields and approval gates needed before `DEPLOYMENT_STATUS.md` can
> change. It does not declare public health, mutate deployment status, write a
> declaration receipt, record endpoint values, record approval references,
> record dates, claim validation pass, append evidence, publish artifacts, open
> access, move money, make legal/business claims, publish externally, or
> deploy.

Witness packet: [`../examples/foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json)

Rule: Public health declaration rehearsal is a local field-label map for a
future declaration receipt. It is not a public health declaration, not a
deployment status mutation, not operator approval, not live evidence, and not
deployment readiness.

No public health declaration, deployment status mutation, declaration receipt
writing, deployment witness publication claim, public health endpoint value,
operator approval reference value, audited-date value, schema-validation pass
claim, closure-validation pass claim, endpoint-match claim, evidence-ledger
append, workflow dispatch, artifact publication, readiness claim, customer
access, personal-data collection, money movement, legal-clearance claim,
company-formation claim, patent claim, external publication, or deployment
claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 remains blocked by `production_health_not_declared`, but Foundation
Mode must not flip status or invent approval. This boundary makes the future
declaration receipt shape visible while keeping the declaration itself blocked
until a published deployment witness, matching health endpoint evidence,
operator approval, and governed validators exist.

Use it when the question is:

1. Which public health declaration receipt fields must exist later?
2. Which `DEPLOYMENT_STATUS.md` mutation gate stays blocked today?
3. Which public health endpoint and approval reference values must stay out of
   Git?
4. Which schema and closure validations must remain future evidence?
5. Which reassessment gate prevents rehearsal labels from becoming status
   proof?

## Current State

```text
public_health_declaration_rehearsal_state=AwaitingEvidence
public_health_declared=false
deployment_status_mutation_allowed=false
declaration_receipt_written=false
deployment_witness_publication_claimed=false
deployment_witness_state_value_recorded=false
public_health_endpoint_value_recorded=false
operator_approval_ref_value_recorded=false
audited_date_value_recorded=false
schema_validation_pass_claimed=false
closure_validation_pass_claimed=false
endpoint_match_claimed=false
dry_run_result_recorded=false
status_update_result_recorded=false
evidence_ledger_append_allowed=false
workflow_dispatch_allowed=false
artifact_publication_allowed=false
readiness_claimed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Declaration Field Labels

These labels are receipt fields only. They are not status mutations, endpoint
values, approval references, dates, validation results, evidence-ledger
entries, workflow run ids, artifact ids, deployment witness ids, or production
health evidence.

| Label | Later declaration field | Boundary |
| --- | --- | --- |
| `deployment_status_path_label` | Future status document field label. | Do not mutate status. |
| `deployment_witness_path_label` | Future deployment witness field label. | Do not claim witness publication. |
| `declaration_receipt_path_label` | Future declaration receipt field label. | Do not write a declaration receipt. |
| `dry_run_flag_label` | Future dry-run field label. | Do not record dry-run outcomes. |
| `updated_flag_label` | Future update-result field label. | Do not record status updates. |
| `deployment_witness_state_label` | Future witness-state field label. | Do not record state values. |
| `public_health_endpoint_label` | Future endpoint field label. | Do not record endpoint values. |
| `operator_approval_ref_label` | Future approval-reference field label. | Do not record approval references. |
| `audited_date_label` | Future audited-date field label. | Do not record dates. |
| `schema_validation_result_label` | Future schema-validation field label. | Do not claim schema pass. |
| `closure_validation_result_label` | Future closure-validation field label. | Do not claim closure pass. |
| `endpoint_match_result_label` | Future endpoint-match field label. | Do not claim endpoint match. |
| `evidence_ledger_route_label` | Future evidence-ledger route label. | Do not append evidence. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve declaration or deployment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Deployment status path label | Record the field label only. | Do not mutate `DEPLOYMENT_STATUS.md`. |
| Deployment witness path label | Record the field label only. | Do not claim deployment witness publication. |
| Declaration receipt path label | Record the field label only. | Do not write declaration receipts. |
| Dry-run flag label | Record the field label only. | Do not record dry-run outcomes. |
| Updated flag label | Record the field label only. | Do not record status updates. |
| Deployment witness state label | Record the field label only. | Do not record state values. |
| Public health endpoint label | Record the field label only. | Do not record endpoint values. |
| Operator approval reference label | Record the field label only. | Do not record approval references. |
| Audited date label | Record the field label only. | Do not record dates. |
| Schema validation result label | Record the field label only. | Do not claim schema pass. |
| Closure validation result label | Record the field label only. | Do not claim closure pass. |
| Endpoint match result label | Record the field label only. | Do not claim endpoint match. |
| Evidence ledger route label | Record the route label only. | Do not append evidence. |
| Operator reassessment gate | Record the gate label only. | Do not approve declaration or deployment. |

## Operator Procedure

1. Treat this boundary as a declaration-shape rehearsal, not a status update.
2. Keep only public-safe field labels and blocked-gate notes in Git.
3. Do not place public health endpoint values, gateway URLs, deployment witness
   ids, declaration receipt ids, approval references, audited dates, validation
   results, workflow run ids, artifact ids, secret values, provider
   identifiers, account identifiers, personal data, payment details, private
   paths, or customer information in this witness.
4. Stop if the next step requires public health declaration, deployment status
   mutation, declaration receipt writing, endpoint value recording, approval
   reference recording, date recording, validation-pass claiming,
   evidence-ledger append, workflow dispatch, artifact publication, readiness
   promotion, customer access, payment, legal/business action, publication, or
   deployment.
5. Keep the rehearsal in `AwaitingEvidence` until a published deployment
   witness, endpoint evidence receipt, public health declaration receipt,
   operator approval receipt, status mutation receipt, evidence-ledger append
   receipt, and reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_public_health_declaration_rehearsal_boundary.py
```

The validator checks that the public health declaration rehearsal witness:

1. keeps every declaration field surface in `AwaitingEvidence`;
2. keeps public health declaration, deployment status mutation, declaration
   receipt writing, witness publication claims, endpoint values, approval
   references, dates, validation-pass claims, endpoint-match claims,
   evidence-ledger append, workflow dispatch, artifact publication, readiness,
   customer access, money, legal/business claims, publication, and deployment
   blocked;
3. allows only public-safe declaration field labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, approval references, status values,
   validation-result values, and assignment shapes for endpoints, witnesses,
   declarations, approvals, dates, statuses, validations, ledgers, workflows,
   artifacts, customers, money, legal/business facts, and deployment facts; and
5. rejects public health, status mutation, approval, validation, evidence,
   publication, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse endpoint evidence receipt fields | [Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md) |
| Route deployment witness evidence slots | [Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md) |
| Name deployment witness evidence slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Record local evidence references | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: public health declaration blocked, deployment status mutation blocked, declaration receipt writing blocked, deployment witness publication claim blocked, endpoint value blocked, approval reference blocked, audited-date value blocked, validation-pass claims blocked, endpoint-match claim blocked, evidence-ledger append blocked, workflow dispatch blocked, artifact publication blocked, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all public health declaration rehearsal surfaces remain AwaitingEvidence
  Next action: validate this declaration-shape rehearsal before any future public health declaration or deployment status mutation work
