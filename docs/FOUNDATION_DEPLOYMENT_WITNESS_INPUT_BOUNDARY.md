<!--
Purpose: define the Foundation Mode boundary for deployment witness runtime input preparation without collecting live values or changing external state.
Governance scope: issue #330, deployment witness input inventory, runtime witness secret-name handling, conformance secret-name handling, gateway target variables, endpoint contracts, workflow dispatch blocking, artifact-publication blocking, status-claim blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md, examples/foundation_deployment_witness_input_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_witness_input_boundary.py.
Invariants: no secret value, no repository variable value, no DNS mutation, no endpoint reachability claim, no workflow dispatch, no witness artifact publication, no deployment status promotion, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Witness Input Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment witness input preparation means listing the
> future evidence categories needed by issue #330. It does not collect secret
> values, bind repository variables, mutate DNS, dispatch workflows, prove
> endpoint reachability, publish a witness artifact, update deployment status,
> open access, spend money, make legal/business claims, or deploy.

Witness packet: [`../examples/foundation_deployment_witness_input_witness.awaiting_evidence.json`](../examples/foundation_deployment_witness_input_witness.awaiting_evidence.json)

Rule: Deployment witness inputs are local placeholders only. Variable names,
secret names, and endpoint contract labels may be documented, but live values
and external actions remain blocked.

No secret value, repository variable value, DNS mutation, endpoint reachability
claim, workflow dispatch, deployment witness artifact publication, deployment
status promotion, customer access, personal-data collection, money movement,
legal-clearance claim, company-formation claim, patent claim, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 asks for live runtime inputs before a deployment witness can be
published. In Foundation Mode, those inputs are not ready and should not be
collected inside repository docs. This boundary keeps the issue understandable
at an atomic level while preserving the current safe state.

Use it when the question is:

1. Which future deployment witness inputs are missing?
2. Which names are public-safe to remember?
3. Which values must stay outside Git and outside local docs?
4. Which endpoint contracts must later be reachable?
5. Which workflow and status transitions must remain blocked until external
   operator evidence exists?

## Current State

```text
deployment_witness_input_state=AwaitingEvidence
runtime_witness_secret_value_allowed=false
runtime_conformance_secret_value_allowed=false
gateway_url_value_allowed=false
expected_runtime_env_value_allowed=false
repository_variable_binding_allowed=false
dns_mutation_allowed=false
endpoint_reachability_claimed=false
workflow_dispatch_allowed=false
witness_artifact_publication_allowed=false
deployment_status_promotion_allowed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Names

These names are public-safe labels only; this document must not contain live
values for them.

| Name | Role | Boundary |
| --- | --- | --- |
| `MULLU_RUNTIME_WITNESS_SECRET` | Future runtime witness secret name. | Secret value must stay outside Git and outside this document. |
| `MULLU_RUNTIME_CONFORMANCE_SECRET` | Future runtime conformance secret name. | Secret value must stay outside Git and outside this document. |
| `MULLU_GATEWAY_URL` | Future gateway base URL variable name. | URL value must stay `AwaitingEvidence`. |
| `MULLU_EXPECTED_RUNTIME_ENV` | Future runtime environment variable name. | Environment value must stay `AwaitingEvidence`. |
| `/health` | Future health endpoint contract. | Reachability is not claimed. |
| `/gateway/witness` | Future witness endpoint contract. | Required fields are not claimed. |
| `/runtime/conformance` | Future conformance endpoint contract. | HMAC verification is not claimed. |

## Input Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Runtime witness secret name | Record the public-safe secret name only. | Do not record, read, print, copy, or validate the secret value. |
| Runtime conformance secret name | Record the public-safe secret name only. | Do not record, read, print, copy, or validate the secret value. |
| Gateway URL variable name | Record that a future gateway URL variable is required. | Do not record a live URL value or claim DNS readiness. |
| Expected runtime environment variable name | Record that a future environment value is required. | Do not select or bind a live environment value. |
| Health endpoint contract | Record the endpoint path contract. | Do not claim endpoint reachability or production health. |
| Gateway witness endpoint contract | Record the endpoint path contract. | Do not claim witness fields, HMAC pass, or artifact publication. |
| Runtime conformance endpoint contract | Record the endpoint path contract. | Do not claim conformance fields or HMAC pass. |
| Repository variable binding gate | Record that variables must later be bound through governed tooling. | Do not bind variables or dispatch workflows. |
| Workflow dispatch gate | Record the dispatch preconditions. | Do not run Deployment Witness Collection or gateway publication workflows. |
| Artifact publication gate | Record the future artifact validation condition. | Do not claim `deployment_claim: published`. |
| Deployment status claim gate | Record the future status-promotion condition. | Do not update public deployment status to healthy or published. |
| Operator handoff | Record why external operator evidence is still required. | Do not cross into DNS, runtime, provider, money, secret, or legal action. |

## Operator Procedure

1. Treat this boundary as an inventory, not a runbook.
2. Keep only public-safe names and endpoint paths in Git.
3. Do not place real URL values, environment values, provider identifiers,
   secret values, private file paths, tokens, or account details in this
   witness.
4. Stop if the next step requires DNS mutation, runtime provisioning,
   repository variable binding, workflow dispatch, endpoint probing with a
   claimed result, secret handling, customer access, payment, legal/business
   action, publication, or deployment.
5. Keep issue #330 in `AwaitingEvidence` until an external operator thread
   supplies the live evidence and governed required validators pass.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_witness_input_boundary.py
```

The validator checks that the deployment witness input witness:

1. keeps all live values and external actions blocked;
2. keeps every input surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. allows only public-safe names and endpoint contract labels; and
5. rejects live URL values, private paths, email-like identifiers, assignment
   shapes for secrets, tokens, providers, variables, accounts, DNS targets,
   workflow runs, endpoint readiness, payment, legal/business facts, customer
   data, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |
| Record evidence without closure claims | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: secret values blocked, repository variable values blocked, DNS mutation blocked, endpoint reachability claims blocked, workflow dispatch blocked, witness artifact publication blocked, deployment status promotion blocked, customer access blocked, personal-data collection blocked, money movement blocked, legal-clearance claim blocked, company-formation claim blocked, patent claim blocked, external publication blocked, deployment blocked
  Open issues: runtime witness secret placement evidence, runtime conformance secret placement evidence, gateway URL evidence, expected runtime environment evidence, endpoint reachability evidence, HMAC verification evidence, repository variable binding evidence, workflow dispatch evidence, published witness artifact evidence, and deployment status evidence remain AwaitingEvidence
  Next action: run the deployment witness input validator before using issue #330 inputs as a local prerequisite inventory
