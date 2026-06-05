<!--
Purpose: define the Foundation Mode boundary for rehearsing deployment witness artifact-validation gates without downloading, validating, uploading, publishing, or promoting any live artifact.
Governance scope: issue #330, deployment witness artifact-validation rehearsal, schema label routing, deployment_claim gate blocking, HMAC proof blocking, public health proof blocking, closure-validation blocking, evidence-ledger append blocking, operator approval blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md, examples/foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary.py.
Invariants: no artifact download, no artifact path value, no artifact id value, no artifact digest value, no schema-validation claim, no deployment_claim publication claim, no runtime HMAC verification claim, no conformance HMAC verification claim, no public health endpoint claim, no closure-validation claim, no evidence-ledger append, no workflow run claim, no operator approval, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Witness Artifact Validation Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment witness artifact validation rehearsal means naming
> the future uploaded-artifact validation gates for issue #330. It does not
> download a workflow artifact, record an artifact path, record an artifact id,
> record a digest, validate a schema, prove `deployment_claim: published`,
> verify HMAC fields, verify public endpoints, append evidence, approve
> operators, publish externally, or deploy.

Witness packet: [`../examples/foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json)

Rule: Deployment witness artifact validation rehearsal is a local map of future
artifact-validation gates. It is not a downloaded artifact, not a schema pass,
not a `deployment_claim: published` proof, not runtime HMAC proof, not public
health proof, not evidence-ledger append, not operator approval, and not
deployment readiness.

No artifact download, artifact path value, artifact id value, artifact digest
value, schema-validation claim, `deployment_claim: published` claim, runtime
HMAC verification claim, conformance HMAC verification claim, public health
endpoint claim, closure-validation claim, evidence-ledger append, workflow run
claim, operator approval, customer access, personal-data collection, money
movement, legal-clearance claim, company-formation claim, patent claim,
external publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 eventually requires the uploaded `Deployment Witness Collection`
artifact to validate against `schemas/deployment_witness.schema.json` and to
contain `deployment_claim: published`. In Foundation Mode, there is no uploaded
artifact to inspect yet. This boundary lets the repository prepare the exact
future checks without pretending the artifact exists or has passed.

Use it when the question is:

1. Which future artifact label is inspected after the manual workflow run?
2. Which schema label is used for the future validation?
3. Which `deployment_claim` value gate remains blocked?
4. Which runtime and conformance HMAC gates remain blocked?
5. Which evidence-ledger and operator gates prevent accidental promotion?

## Current State

```text
deployment_witness_artifact_validation_rehearsal_state=AwaitingEvidence
artifact_download_allowed=false
artifact_path_recorded=false
artifact_id_recorded=false
artifact_digest_recorded=false
artifact_schema_validation_claimed=false
deployment_claim_published_claimed=false
runtime_hmac_verified=false
conformance_hmac_verified=false
public_health_endpoint_claimed=false
closure_validation_claimed=false
evidence_ledger_append_allowed=false
workflow_run_claimed=false
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

## Public-Safe Validation Labels

These labels are safe to keep in Git because they are template names and gate
names, not live artifact values.

| Label | Future role | Boundary |
| --- | --- | --- |
| `.change_assurance/deployment_witness.json` | Future local artifact template label. | Do not record a live artifact path. |
| `schemas/deployment_witness.schema.json` | Future deployment witness schema label. | Do not claim schema validation. |
| `deployment_claim` | Future artifact field label. | Do not claim the field exists in a live artifact. |
| `published` | Future required value label. | Do not claim the value was observed. |
| `scripts/validate_deployment_publication_closure.py` | Future closure-validator label. | Do not claim closure validation. |
| `tests/test_deployment_witness_schema.py` | Future schema-test label. | Do not treat a local test label as live evidence. |
| `tests/test_validate_deployment_publication_closure.py` | Future closure-test label. | Do not treat a local test label as publication evidence. |
| `runtime witness HMAC validation gate` | Future runtime witness HMAC gate. | Do not claim runtime HMAC verification. |
| `runtime conformance HMAC validation gate` | Future conformance HMAC gate. | Do not claim conformance HMAC verification. |
| `public health endpoint match gate` | Future public health match gate. | Do not claim endpoint proof. |
| `evidence ledger append gate` | Future evidence-ledger append gate. | Do not append or promote evidence. |
| `operator reassessment gate` | Future operator decision gate. | Do not claim operator approval. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Artifact path label | Record the future template label. | Do not record a live artifact path. |
| Artifact id slot | Reserve a future artifact-id slot. | Do not record artifact ids. |
| Artifact digest slot | Reserve a future digest slot. | Do not record artifact digests. |
| Deployment witness schema label | Record the schema label. | Do not claim schema validation. |
| Deployment claim field label | Record the `deployment_claim` field label. | Do not claim the field exists in a live artifact. |
| Published value gate label | Record the `published` value gate. | Do not claim the value was observed. |
| Runtime HMAC validation gate | Record the future HMAC gate. | Do not claim runtime HMAC verification. |
| Conformance HMAC validation gate | Record the future conformance HMAC gate. | Do not claim conformance HMAC verification. |
| Public health endpoint match gate | Record the future endpoint match gate. | Do not claim endpoint proof. |
| Closure validator label | Record the closure-validator label. | Do not claim closure validation. |
| Evidence ledger route label | Record the future ledger route. | Do not append or promote evidence. |
| Operator reassessment gate | Record the human reassessment stop rule. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as an artifact-validation rehearsal map, not an artifact
   collector.
2. Keep only public-safe artifact template names, schema names, field names,
   required-value labels, validator labels, and gate labels in Git.
3. Do not place live artifact paths, artifact ids, artifact digests, workflow
   run ids, repository variable values, secret values, HMAC values, hosts, URLs,
   provider identifiers, account identifiers, approval ids, personal data, or
   private paths in this witness.
4. Stop if the next step requires artifact download, schema validation,
   runtime HMAC verification, conformance HMAC verification, endpoint proof,
   closure validation, evidence-ledger append, operator approval, customer
   access, payment, legal/business action, publication, or deployment.
5. Keep issue #330 in `AwaitingEvidence` until an external operator thread
   supplies a live workflow run, uploaded artifact, artifact digest, schema
   validation receipt, `deployment_claim: published` receipt, HMAC validation
   receipts, public health evidence, closure validation receipt, and operator
   approval reference.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary.py
```

The validator checks that the deployment witness artifact validation rehearsal
witness:

1. keeps artifact download, artifact path, artifact id, artifact digest, schema
   validation, deployment-claim publication, HMAC verification, public health,
   closure validation, evidence append, workflow run, approval, customer,
   money, legal, publication, and deployment surfaces blocked;
2. keeps every artifact-validation surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. allows only public-safe artifact-validation labels and gate labels; and
5. rejects URLs, private paths, email-like identifiers, live assignment shapes,
   artifact download or validation phrases, HMAC proof phrases, endpoint proof
   phrases, evidence append phrases, approval phrases, and deployment claims.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse workflow dispatch labels | [Foundation Deployment Witness Dispatch Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md) |
| Prepare evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Route future evidence without ledger append | [Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md) |
| Record local evidence references | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: artifact download blocked, artifact path value blocked, artifact id value blocked, artifact digest value blocked, schema-validation claim blocked, deployment-claim publication blocked, runtime HMAC verification blocked, conformance HMAC verification blocked, public health endpoint claim blocked, closure-validation claim blocked, evidence-ledger append blocked, workflow run claim blocked, operator approval blocked, customer access blocked, personal-data collection blocked, money movement blocked, legal-clearance claim blocked, company-formation claim blocked, patent claim blocked, external publication blocked, deployment blocked
  Open issues: live workflow run evidence, uploaded artifact evidence, artifact digest evidence, schema-validation receipt, deployment_claim publication receipt, HMAC validation receipts, public health evidence, closure-validation receipt, evidence-ledger append approval, operator approval, and deployment status evidence remain AwaitingEvidence
  Next action: run the deployment witness artifact validation rehearsal validator before using artifact-validation labels as a local prerequisite checklist
