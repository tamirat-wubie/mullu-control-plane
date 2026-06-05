<!--
Purpose: define the Foundation Mode boundary for rehearsing deployment witness workflow dispatch without running workflows, mutating GitHub state, handling secrets, publishing artifacts, or deploying.
Governance scope: issue #330, deployment witness workflow dispatch rehearsal, manual workflow input labels, GitHub mutation blocking, workflow-run claim blocking, dispatch receipt blocking, artifact validation blocking, operator approval blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md, examples/foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_witness_dispatch_rehearsal_boundary.py.
Invariants: no workflow dispatch, no GitHub API mutation, no manual workflow execution, no live gateway URL value, no expected-environment value, no workflow ref value, no workflow run id, no dispatch receipt, no secret value, no secret-presence claim, no repository variable binding, no artifact publication, no deployment-claim publication, no deployment status promotion, no operator approval, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Witness Dispatch Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment witness dispatch rehearsal means naming the future
> manual workflow dispatch fields for issue #330. It does not run GitHub
> workflows, mutate repository variables, read or claim secrets, publish
> artifacts, approve status, open access, spend money, make legal/business
> claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json)

Rule: Dispatch rehearsal is a local stop-rule map for the later manual
`Deployment Witness Collection` workflow. It is not workflow execution, not a
GitHub mutation receipt, not deployment witness evidence, and not readiness.

No workflow dispatch, GitHub API mutation, manual workflow execution, live
gateway URL value, expected-environment value, workflow ref value, workflow run
id, dispatch receipt, secret value, secret-presence claim, repository variable
binding, artifact publication, `deployment_claim: published` claim, deployment
status promotion, operator approval, customer access, personal-data collection,
money movement, legal-clearance claim, company-formation claim, patent claim,
external publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 eventually requires the manual `Deployment Witness Collection`
workflow to run with a gateway URL and expected environment. In Foundation
Mode, that step is not allowed yet. This boundary lets the repository prepare
the dispatch labels and stop rules without crossing into GitHub workflow
mutation or live evidence collection.

Use it when the question is:

1. Which manual workflow is eventually dispatched?
2. Which workflow input labels are required later?
3. Which preflight evidence must exist before dispatch is allowed?
4. Which workflow-run and artifact claims remain blocked?
5. Which operator reassessment gate stops accidental promotion?

## Current State

```text
deployment_witness_dispatch_rehearsal_state=AwaitingEvidence
workflow_dispatch_allowed=false
github_api_mutation_allowed=false
manual_workflow_execution_allowed=false
gateway_url_value_allowed=false
expected_environment_value_recorded=false
workflow_ref_value_recorded=false
workflow_run_id_recorded=false
dispatch_receipt_recorded=false
secret_value_allowed=false
secret_presence_claimed=false
repository_variable_binding_allowed=false
workflow_run_claimed=false
artifact_publication_allowed=false
deployment_claim_published_claimed=false
deployment_status_promotion_allowed=false
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

## Public-Safe Dispatch Labels

These labels are safe to keep in Git because they are names, not values.

| Label | Future role | Boundary |
| --- | --- | --- |
| `scripts/dispatch_deployment_witness.py` | Future dispatch helper label. | Do not run it against live repository state. |
| `.github/workflows/deployment-witness.yml` | Future manual workflow file label. | Do not dispatch it. |
| `Deployment Witness Collection` | Future workflow display-name label. | Do not claim a workflow run exists. |
| `gateway_url` | Future workflow input label. | Do not record the live gateway URL value. |
| `expected_environment` | Future workflow input label. | Do not record the expected-environment value. |
| `MULLU_GATEWAY_URL` | Future repository variable-name label. | Do not bind or verify the variable. |
| `MULLU_EXPECTED_RUNTIME_ENV` | Future repository variable-name label. | Do not bind or verify the variable. |
| `schemas/deployment_witness.schema.json` | Future artifact schema label. | Do not claim artifact validation. |
| `scripts/validate_deployment_publication_closure.py` | Future closure-validator label. | Do not claim closure pass. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Preflight dependency label | Record that preflight must pass later. | Do not claim preflight pass. |
| Workflow file label | Record the workflow file label. | Do not call GitHub workflow APIs. |
| Workflow name label | Record the workflow display-name label. | Do not claim workflow lookup. |
| Gateway URL input label | Record the input field name. | Do not record a URL value. |
| Expected environment input label | Record the input field name. | Do not record an environment value. |
| Repository variable dependency label | Record future variable-name labels. | Do not bind, verify, or update repository variables. |
| Secret dependency label | Record that secrets are external prerequisites. | Do not read, print, copy, validate, or claim secrets. |
| Manual dispatch command label | Record the dispatch helper label. | Do not execute dispatch. |
| Dispatch receipt slot | Reserve a future receipt slot. | Do not record a dispatch receipt. |
| Workflow run receipt slot | Reserve a future run receipt slot. | Do not record run ids or claim runs. |
| Artifact validation dependency label | Record the schema and closure validator labels. | Do not claim artifact validation. |
| Deployment-claim publication gate | Record the `deployment_claim: published` gate label. | Do not claim publication. |
| Operator reassessment gate | Record the human reassessment stop rule. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as a dispatch rehearsal map, not a dispatch runner.
2. Keep only public-safe script names, workflow names, input names, schema names,
   variable names, and gate labels in Git.
3. Do not place real hosts, URLs, workflow refs, run ids, artifact ids, secret
   values, provider identifiers, account identifiers, private paths, or approval
   references in this witness.
4. Stop if the next step requires GitHub workflow dispatch, GitHub API mutation,
   repository variable binding, secret handling, live URL values, run receipts,
   artifact upload, status promotion, customer access, payment, legal/business
   action, external publication, or deployment.
5. Keep issue #330 in `AwaitingEvidence` until an external operator thread
   supplies live evidence and the governed required validators pass.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_witness_dispatch_rehearsal_boundary.py
```

The validator checks that the deployment witness dispatch rehearsal witness:

1. keeps workflow dispatch, GitHub mutation, live input values, secrets,
   repository variables, workflow runs, artifacts, status, approval, customer,
   money, legal, publication, and deployment surfaces blocked;
2. keeps every dispatch rehearsal surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. allows only public-safe dispatch labels and gate labels; and
5. rejects URL values, private paths, email-like identifiers, assignments for
   live values, run receipts, artifact ids, approvals, promotion phrases, and
   deployment claims.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Inventory deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Rehearse deployment witness preflight | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Prepare evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Route future evidence without ledger append | [Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: workflow dispatch blocked, GitHub API mutation blocked, manual workflow execution blocked, gateway URL value blocked, expected-environment value blocked, workflow ref value blocked, workflow run id blocked, dispatch receipt blocked, secret value blocked, secret presence claim blocked, repository variable binding blocked, workflow run claim blocked, artifact publication blocked, deployment-claim publication blocked, deployment status promotion blocked, operator approval blocked, customer access blocked, personal-data collection blocked, money movement blocked, legal-clearance claim blocked, company-formation claim blocked, patent claim blocked, external publication blocked, deployment blocked
  Open issues: preflight pass evidence, repository variable binding evidence, secret placement evidence, dispatch receipt evidence, workflow run evidence, deployment witness artifact evidence, schema-validation evidence, closure-validation evidence, operator approval evidence, and deployment status evidence remain AwaitingEvidence
  Next action: run the deployment witness dispatch rehearsal validator before using dispatch labels as a local prerequisite checklist
