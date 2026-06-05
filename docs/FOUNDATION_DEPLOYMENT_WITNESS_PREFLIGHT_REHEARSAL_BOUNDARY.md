<!--
Purpose: define the Foundation Mode boundary for rehearsing deployment witness preflight checks without live probing, workflow dispatch, secret handling, or deployment.
Governance scope: issue #330, deployment witness preflight rehearsal, gateway publication readiness command labels, closure-plan command labels, required-validator fail-closed behavior, DNS probe blocking, endpoint probe blocking, repository variable binding blocking, workflow dispatch blocking, artifact publication blocking, status-promotion blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md, examples/foundation_deployment_witness_preflight_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_witness_preflight_rehearsal_boundary.py.
Invariants: no live preflight execution, no live URL value, no DNS probe, no endpoint probe, no secret value, no secret presence claim, no repository variable binding, no workflow dispatch, no readiness report claim, no witness artifact publication, no deployment status promotion, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Witness Preflight Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment witness preflight rehearsal means naming the
> future fail-closed checks for issue #330. It does not run live preflight,
> probe DNS, probe endpoints, read or claim secrets, bind repository variables,
> dispatch workflows, publish artifacts, promote deployment status, open access,
> spend money, make legal/business claims, or deploy.

Witness packet: [`../examples/foundation_deployment_witness_preflight_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_deployment_witness_preflight_rehearsal_witness.awaiting_evidence.json)

Rule: Preflight rehearsal is a local checklist of command labels and blocked
gates. It is not live preflight execution, not endpoint evidence, and not a
deployment witness.

No live preflight execution, live URL value, DNS probe, endpoint probe, secret
value, secret presence claim, repository variable binding, workflow dispatch,
readiness report claim, deployment witness artifact publication, deployment
status promotion, customer access, personal-data collection, money movement,
legal-clearance claim, company-formation claim, patent claim, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

After the deployment witness input inventory is visible, the next risk is
treating a future preflight command as if it were already run. This boundary
keeps issue #330 preflight work at rehearsal level: public-safe script labels,
blocked live checks, and fail-closed expectations only.

Use it when the question is:

1. Which future preflight commands matter?
2. Which required checks must fail closed until live evidence exists?
3. Which live probes are still not allowed in Foundation Mode?
4. Which status or artifact claims remain blocked?
5. Which operator handoff evidence is still outside this local thread?

## Current State

```text
deployment_witness_preflight_rehearsal_state=AwaitingEvidence
live_preflight_execution_allowed=false
live_gateway_url_value_allowed=false
dns_probe_allowed=false
endpoint_probe_allowed=false
secret_value_allowed=false
secret_presence_claimed=false
repository_variable_binding_allowed=false
workflow_dispatch_allowed=false
readiness_report_claimed=false
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

## Public-Safe Command Labels

These are local script or workflow labels only; this document must not include
live arguments, live hosts, secret values, provider identifiers, run ids, or
artifact ids.

| Label | Future role | Boundary |
| --- | --- | --- |
| `scripts/preflight_deployment_witness.py` | Future deployment witness preflight command. | Do not run live preflight or claim readiness. |
| `scripts/report_gateway_publication_readiness.py` | Future gateway publication readiness reporter. | Do not claim report readiness. |
| `scripts/plan_deployment_publication_closure.py` | Future closure-plan command. | Do not claim closure. |
| `scripts/validate_deployment_publication_closure_plan_schema.py` | Future closure-plan schema validator. | Schema validation is not live evidence. |
| `.github/workflows/deployment-witness.yml` | Future deployment witness workflow label. | Do not dispatch workflow. |
| `.github/workflows/gateway-publication.yml` | Future gateway publication workflow label. | Do not dispatch workflow. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Deployment preflight command label | Record the future command label. | Do not run it against live gateway input. |
| Gateway publication readiness label | Record the future reporter label. | Do not claim readiness report pass. |
| Closure plan command label | Record the future closure-plan label. | Do not claim closure plan approval. |
| Closure plan schema label | Record the future schema-validator label. | Do not treat schema validity as live evidence. |
| Required-validator fail-closed check | Record that required validators must fail closed until evidence exists. | Do not bypass required validators. |
| DNS probe gate | Record that DNS evidence is still missing. | Do not run or claim DNS resolution. |
| Endpoint probe gate | Record that endpoint evidence is still missing. | Do not probe or claim `/health`, `/gateway/witness`, or `/runtime/conformance`. |
| Secret presence gate | Record that secret presence evidence is external. | Do not read, print, copy, validate, or claim secret values. |
| Repository variable gate | Record that variable binding is external. | Do not create, update, verify, or bind repository variables. |
| Workflow dispatch gate | Record that workflow dispatch is external. | Do not dispatch deployment witness or gateway publication workflows. |
| Artifact publication gate | Record that witness artifact evidence is missing. | Do not publish, upload, or promote witness artifacts. |
| Deployment status gate | Record that status promotion is blocked. | Do not update deployment status to healthy or published. |
| Operator handoff | Record that live evidence belongs to an external operator thread. | Do not cross DNS, runtime, provider, money, secret, legal, publication, or deployment boundaries. |

## Operator Procedure

1. Treat this boundary as a rehearsal checklist, not a command runner.
2. Keep only public-safe script names, workflow names, and gate labels in Git.
3. Do not place real hosts, URLs, provider identifiers, repository variable
   values, secret values, run ids, artifact ids, account identifiers, or private
   paths in this witness.
4. Stop if the next step requires live preflight execution, DNS probing,
   endpoint probing, secret handling, repository variable mutation, workflow
   dispatch, artifact upload, status promotion, customer access, payment,
   legal/business action, publication, or deployment.
5. Keep issue #330 in `AwaitingEvidence` until an external operator thread
   supplies live evidence and the governed required validators pass.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_witness_preflight_rehearsal_boundary.py
```

The validator checks that the deployment witness preflight rehearsal witness:

1. keeps live preflight, DNS, endpoint, secret, repository variable, workflow,
   artifact, status, customer, money, legal, publication, and deployment
   surfaces blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. allows only public-safe command labels and gate labels; and
5. rejects live URL values, private paths, email-like identifiers, assignment
   shapes for secrets, tokens, providers, variables, accounts, DNS targets,
   workflow runs, readiness reports, artifacts, customer data, money,
   legal/business facts, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Inventory deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |
| Record evidence without closure claims | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: live preflight execution blocked, live gateway URL values blocked, DNS probe blocked, endpoint probe blocked, secret value blocked, secret presence claim blocked, repository variable binding blocked, workflow dispatch blocked, readiness report claim blocked, witness artifact publication blocked, deployment status promotion blocked, customer access blocked, personal-data collection blocked, money movement blocked, legal-clearance claim blocked, company-formation claim blocked, patent claim blocked, external publication blocked, deployment blocked
  Open issues: live gateway URL evidence, DNS resolution evidence, endpoint reachability evidence, runtime witness secret placement evidence, runtime conformance secret placement evidence, repository variable binding evidence, workflow dispatch evidence, published witness artifact evidence, and deployment status evidence remain AwaitingEvidence
  Next action: run the deployment witness preflight rehearsal validator before using preflight labels as a local prerequisite checklist
