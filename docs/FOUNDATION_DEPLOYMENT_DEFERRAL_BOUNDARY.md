<!--
Purpose: define the Foundation Mode deployment-deferral boundary before any deployment planning, cloud activation, public endpoint, production health, customer access, spending, secret use, or readiness claim.
Governance scope: deployment deferral, local prerequisite questions, public-health blocking, cloud/runtime exposure blocking, cost blocking, credential blocking, customer-access blocking, rollback-readiness caution, and external-publication restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md, examples/foundation_deployment_deferral_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_deferral_boundary.py.
Invariants: no deployment-plan approval, no cloud activation, no public endpoint claim, no production-health claim, no runtime-readiness claim, no customer-access claim, no spending authorization, no credential use, no secret use, no migration execution, no DNS mutation, no external publication, and no deployment claim.
-->

# Foundation Deployment Deferral Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** deployment deferral means the project is intentionally not
> moving toward live hosting yet. You may draft local prerequisite questions
> about what a future deployment would require, but this boundary does not
> approve a deployment plan, activate cloud resources, open endpoints, claim
> production health, spend money, use credentials, invite customers, publish
> externally, or deploy.

Witness packet: [`../examples/foundation_deployment_deferral_witness.awaiting_evidence.json`](../examples/foundation_deployment_deferral_witness.awaiting_evidence.json)

Rule: Deployment deferral is a local planning boundary, not a deployment plan, production-health certificate, customer-access approval, spending approval, credential-use approval, publication approval, or readiness certificate.

No deployment plan approval, cloud activation, public endpoint, production
health, runtime readiness, customer access, spending authorization, credential
use, secret use, migration execution, DNS mutation, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Deployment is where local preparation can accidentally become real exposure:
cloud bills, public endpoints, public trust, support duty, data handling,
secret use, DNS changes, and irreversible operational state. Foundation Mode is
not ready for that. This boundary keeps deployment as a deferred evidence
problem.

This boundary keeps the work small:

1. Draft local deployment prerequisite questions only.
2. Keep cloud, runtime, endpoint, DNS, credential, budget, customer, legal, and
   rollback surfaces in `AwaitingEvidence`.
3. Keep public-health and deployment-readiness language blocked.
4. Keep all provider-specific values, endpoint values, private paths,
   credentials, customers, and schedules out of public artifacts.

## Current State

```text
deployment_deferral_boundary_state=AwaitingEvidence
deployment_plan_approved=false
cloud_activation_allowed=false
public_endpoint_allowed=false
production_health_claimed=false
runtime_readiness_claimed=false
customer_access_allowed=false
spending_allowed=false
credential_use_allowed=false
secret_use_allowed=false
migration_execution_allowed=false
dns_mutation_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Deferral Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Deployment prerequisite map | List local evidence categories needed before deployment discussion. | Do not approve or schedule deployment. |
| Hosting and cloud questions | List cloud-risk questions only. | Do not activate cloud resources or bind providers. |
| Endpoint exposure questions | Name exposure concerns. | Do not publish URLs, ports, routes, DNS targets, or public endpoints. |
| Runtime health questions | Draft health-check categories. | Do not claim production health, uptime, or public-health readiness. |
| Rollback and recovery questions | Draft rollback questions. | Do not claim rollback readiness or incident coverage. |
| Cost and billing questions | Draft cost-control questions. | Do not authorize spending, billing, subscriptions, or payment methods. |
| Credential and secret questions | Draft credential categories. | Do not create, store, activate, or use real credentials or secrets. |
| Customer and support questions | Draft access/support prerequisites. | Do not invite customers, open support, or claim support readiness. |
| Publication questions | Draft publication blockers. | Do not publish externally or claim launch readiness. |

## Operator Procedure

1. Treat deployment as `DelayedByDesign` until local proof, budget, secrets,
   security, backup, support, intake, privacy, legal, and rollback evidence
   exists.
2. Do not start services, open endpoints, mutate DNS, connect cloud runtimes,
   run migrations, activate credentials, spend money, or publish release copy
   through this boundary.
3. Do not record provider account IDs, DNS targets, endpoint URLs, ports,
   private paths, schedules, customers, credentials, or secrets in public
   artifacts.
4. Keep every deployment surface in `AwaitingEvidence` until a later governed
   deployment witness promotes exactly one bounded step.
5. If a future deployment question appears, route it first through this
   deferral boundary, then through the runtime, cost, secrets, security,
   backup, support, intake, privacy, legal, and source-control boundaries.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_deferral_boundary.py
```

The validator checks that the deployment-deferral witness:

1. keeps every deployment surface in `AwaitingEvidence`;
2. blocks deployment approval, cloud activation, public endpoints, production
   health, runtime readiness, customer access, spending, credential use, secret
   use, migration execution, DNS mutation, external publication, and deployment;
3. rejects URL, email, private path, host/port, provider, customer, schedule,
   DNS, credential, secret, billing, or payment-shaped values; and
4. rejects deployment-readiness, launch-readiness, production-health, and
   access-opening phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare runtime questions safely | [Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md) |
| Prepare cost questions safely | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare secrets questions safely | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: deployment plan approval blocked, cloud activation blocked, public endpoint blocked, production-health claim blocked, runtime-readiness claim blocked, customer access blocked, spending blocked, credential use blocked, secret use blocked, migration execution blocked, DNS mutation blocked, external publication blocked, deployment blocked
  Open issues: deployment prerequisite evidence, cloud evidence, endpoint evidence, runtime health evidence, rollback evidence, cost evidence, credential evidence, customer/support evidence, publication evidence, and deployment witness remain AwaitingEvidence
  Next action: run the deployment-deferral boundary validator before any future deployment-planning or deployment-readiness claim
