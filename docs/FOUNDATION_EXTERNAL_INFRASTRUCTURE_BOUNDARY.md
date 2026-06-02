<!--
Purpose: define the Foundation Mode external-infrastructure boundary for issue #330 style DNS, runtime, secret-placement, endpoint, workflow, and witness prerequisites without claiming readiness or performing external actions.
Governance scope: external infrastructure questions, deployment witness input questions, DNS authority questions, gateway target questions, runtime host questions, managed database questions, secret-manager questions, TLS questions, firewall questions, rollback questions, private runtime witness questions, repository variable questions, endpoint reachability questions, workflow dispatch questions, public-safe planning, and deployment-effect blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md, examples/foundation_external_infrastructure_witness.awaiting_evidence.json, scripts/validate_foundation_external_infrastructure_boundary.py.
Invariants: no external-infrastructure completeness claim, no DNS authority verification claim, no DNS target binding, no DNS mutation, no runtime host provisioning, no managed database provisioning, no secret placement verification, no TLS readiness claim, no firewall readiness claim, no rollback verification claim, no endpoint reachability claim, no workflow dispatch, no paid infrastructure activation, no customer access, no external publication, and no deployment claim.
-->

# Foundation External Infrastructure Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** external-infrastructure preparation means drafting local,
> public-safe questions for the outside systems that would be needed before a
> deployment witness can ever be published. It does not change DNS, provision a
> runtime host, place secrets, buy infrastructure, dispatch workflows, publish
> endpoints, invite customers, or deploy.

Witness packet: [`../examples/foundation_external_infrastructure_witness.awaiting_evidence.json`](../examples/foundation_external_infrastructure_witness.awaiting_evidence.json)

Rule: External-infrastructure preparation is a local planning boundary, not an
external-infrastructure-completion, DNS-authority-verification,
DNS-target-binding, DNS-mutation, runtime-host-provisioning,
managed-database-provisioning, secret-placement-verification, TLS-readiness,
firewall-readiness, rollback-verification, endpoint-reachability,
workflow-dispatch, paid-infrastructure, customer-access, publication, or
deployment certificate.

No external-infrastructure completeness, DNS authority verification, DNS target
binding, DNS mutation, runtime host provisioning, managed database provisioning,
secret placement verification, TLS readiness, firewall readiness, rollback
verification, endpoint reachability, workflow dispatch, paid infrastructure,
customer access, external publication, or deployment claim is permitted by this
boundary.

## Why This Exists

Issue #330 remains `AwaitingEvidence` because the remaining work is not a local
code edit. It requires external operator evidence: a real gateway DNS target,
runtime host, runtime secrets placed in the deployed environment, reachable
evidence endpoints, and witness workflow execution after readiness passes.

In Foundation Mode, the safe action is to name those prerequisites without
performing them. This boundary turns "external infrastructure" into small
questions that can be prepared now while all effect-bearing actions stay
blocked.

## Current State

```text
external_infrastructure_boundary_state=AwaitingEvidence
external_infrastructure_complete_claimed=false
dns_authority_verified=false
dns_target_bound=false
dns_mutation_allowed=false
runtime_host_provisioned=false
managed_database_provisioned=false
secret_placement_verified=false
tls_ready_claimed=false
firewall_ready_claimed=false
rollback_verified=false
endpoint_reachability_claimed=false
repository_variable_binding_allowed=false
workflow_dispatch_allowed=false
paid_infrastructure_allowed=false
customer_access_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## External-Infrastructure Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| DNS authority questions | Draft who controls DNS and what approval would be required. | Do not change DNS records or bind DNS targets. |
| Gateway DNS target questions | Draft what evidence is needed before selecting a gateway target. | Do not record target values, provider ids, or host addresses. |
| Runtime host questions | Draft runtime-host prerequisite questions. | Do not provision hosts, clusters, containers, or public endpoints. |
| Managed database questions | Draft data-store prerequisite questions. | Do not create databases, apply schemas, or record database URLs. |
| Secret-manager questions | Draft secret-placement questions by secret name only. | Do not read, print, store, or publish secret values. |
| TLS certificate questions | Draft certificate and HTTPS-readiness questions. | Do not claim TLS readiness or mutate certificate state. |
| Firewall and network questions | Draft network exposure and ingress questions. | Do not open firewall rules or publish ingress. |
| Rollback path questions | Draft rollback and recovery evidence questions. | Do not claim rollback verification. |
| Private runtime witness questions | Draft private witness handoff questions. | Do not expose private witness files or values. |
| Repository variable questions | Draft variable-name and ownership questions. | Do not bind repository variables. |
| Endpoint reachability questions | Draft evidence required for `/health`, `/gateway/witness`, and `/runtime/conformance`. | Do not claim endpoint reachability. |
| Workflow dispatch questions | Draft dispatch prerequisites and stop rules. | Do not dispatch deployment or publication workflows. |

## Operator Procedure

1. Keep every external-infrastructure item in `AwaitingEvidence` until a
   qualified operator supplies explicit evidence.
2. Record only public-safe categories, names, and question text. Do not record
   secret values, DNS targets, provider account identifiers, host addresses,
   database URLs, private recovery values, or customer data.
3. Treat DNS mutation, runtime provisioning, secret placement, repository
   variable binding, workflow dispatch, endpoint probing, paid infrastructure,
   and deployment as blocked actions unless a later explicit request and
   governed evidence authorize one exact step.
4. Use [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md)
   for deployment posture and [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)
   for public-safe DNS/email labels.
5. Keep issue #330 outcome as `AwaitingEvidence` until published-runtime
   witness evidence exists and deployment publication closure validators pass.

## Validation

Run:

```powershell
python scripts/validate_foundation_external_infrastructure_boundary.py
```

The validator checks that the external-infrastructure witness:

1. keeps external-infrastructure completeness, DNS authority, DNS mutation,
   runtime host, database, secret placement, TLS, firewall, rollback, endpoint
   reachability, repository variable binding, workflow dispatch, paid
   infrastructure, customer access, publication, and deployment disabled;
2. keeps every external-infrastructure surface in `AwaitingEvidence`;
3. rejects URL, email, private path, DNS target, host, provider, account,
   secret, database, workflow, customer, publication, or deployment shaped
   values; and
4. rejects readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Keep deployment deferred | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |
| Prepare domain/email labels safely | [Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md) |
| Prepare secrets without values | [Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: external-infrastructure completeness blocked, DNS authority verification blocked, DNS target binding blocked, DNS mutation blocked, runtime host provisioning blocked, managed database provisioning blocked, secret placement verification blocked, TLS readiness blocked, firewall readiness blocked, rollback verification blocked, endpoint reachability blocked, repository variable binding blocked, workflow dispatch blocked, paid infrastructure blocked, customer access blocked, external publication blocked, deployment blocked
  Open issues: DNS authority evidence, gateway target evidence, runtime host evidence, managed database evidence, secret-placement evidence, TLS evidence, firewall evidence, rollback evidence, private runtime witness evidence, repository variable evidence, endpoint reachability evidence, and workflow dispatch evidence remain AwaitingEvidence
  Next action: run the external-infrastructure validator before using these notes as deployment-prerequisite evidence
