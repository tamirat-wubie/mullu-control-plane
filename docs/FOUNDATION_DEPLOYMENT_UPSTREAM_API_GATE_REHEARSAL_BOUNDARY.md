<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 upstream API readiness gate labels without executing live upstream checks or allowing DNS target selection.
Governance scope: issue #330, upstream API readiness rehearsal, local gate labels, upstream reporter execution blocking, target gateway URL value blocking, production dependency value blocking, DNS publication blocking, repository-variable binding blocking, workflow blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md, examples/foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_deployment_upstream_api_gate_rehearsal_boundary.py.
Invariants: no upstream API readiness claim, no upstream reporter execution claim, no require-ready pass claim, no target gateway URL value, no production image value, no runtime host value, no managed PostgreSQL value, no schema-application value, no secret-store value, no deploy-env value, no release-preflight value, no persistence-check value, no firewall value, no TLS certificate value, no rollback-path value, no private runtime witness value, no DNS authority value, no runtime witness closure claim, no API provisioning, no DNS publication, no DNS target selection, no repository-variable binding, no workflow dispatch, no artifact publication, no readiness claim, no customer access, no personal-data collection, no money movement, no legal/company/patent claim, no external publication, and no deployment claim.
-->

# Foundation Deployment Upstream API Gate Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** upstream API gate rehearsal means naming the future readiness
> gate labels that must be satisfied before DNS target selection or deployment
> witness publication. It does not run the upstream reporter, record live
> target values, prove API readiness, provision services, publish DNS, bind
> repository variables, dispatch workflows, publish artifacts, open access,
> move money, make legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json)

Rule: Deployment upstream API gate rehearsal is a local gate-label map for a
future upstream readiness receipt. It is not upstream API readiness, not
`--require-ready` evidence, not DNS target selection, not API provisioning, and
not deployment witness readiness.

No upstream API readiness claim, upstream reporter execution claim,
require-ready pass claim, target gateway URL value, production dependency
value, runtime host value, managed PostgreSQL value, schema-application value,
secret-store value, deploy-env value, release-preflight value,
persistence-check value, firewall value, TLS certificate value, rollback-path
value, private runtime witness value, DNS authority value, runtime witness
closure claim, API provisioning, DNS publication, DNS target selection,
repository-variable binding, workflow dispatch, artifact publication,
readiness claim, customer access, personal-data collection, money movement,
legal/company/patent claim, external publication, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

Issue #330 still requires upstream API readiness before DNS target selection
and deployment witness publication. Foundation Mode must not simulate that
external evidence. This boundary only names the gate labels that a later
operator-owned receipt must close.

Use it when the question is:

1. Which upstream API readiness gates must exist before DNS target selection?
2. Which external production dependencies must stay as labels, not values?
3. Which require-ready result must remain blocked today?
4. Which DNS and deployment actions remain downstream of this gate?
5. Which reassessment gate prevents local labels from becoming readiness
   proof?

## Current State

```text
deployment_upstream_api_gate_rehearsal_state=AwaitingEvidence
upstream_api_ready_claimed=false
upstream_reporter_executed=false
require_ready_pass_claimed=false
target_gateway_url_value_recorded=false
production_image_value_recorded=false
runtime_host_value_recorded=false
managed_postgres_value_recorded=false
schema_application_value_recorded=false
secret_store_value_recorded=false
deploy_env_value_recorded=false
release_preflight_value_recorded=false
persistence_check_value_recorded=false
host_firewall_value_recorded=false
tls_certificate_value_recorded=false
rollback_path_value_recorded=false
private_runtime_witness_value_recorded=false
dns_authority_value_recorded=false
runtime_witness_closure_claimed=false
api_provisioning_allowed=false
dns_publication_allowed=false
dns_target_selection_allowed=false
repository_variable_binding_allowed=false
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

## Public-Safe Gate Labels

These labels are receipt fields only. They are not URLs, hostnames, production
resource identifiers, provider identifiers, secret references, repository
variable values, workflow run identifiers, artifact identifiers, approval
identifiers, or evidence that an upstream runtime exists.

| Label | Later gate | Boundary |
| --- | --- | --- |
| `upstream_reporter_command_label` | Future upstream reporter command label. | Do not execute the reporter. |
| `target_gateway_url_label` | Future target gateway URL field label. | Do not record a URL value. |
| `recovery_witness_gate_label` | Future recovery witness gate label. | Do not claim recovery closure. |
| `production_image_gate_label` | Future production image gate label. | Do not record image values. |
| `runtime_host_gate_label` | Future runtime host gate label. | Do not record host values. |
| `managed_postgres_gate_label` | Future managed PostgreSQL gate label. | Do not record database values. |
| `schema_application_gate_label` | Future schema-application gate label. | Do not claim schema application. |
| `production_secret_store_gate_label` | Future secret-store gate label. | Do not record or claim secrets. |
| `deploy_env_gate_label` | Future deploy-env gate label. | Do not claim deploy-env closure. |
| `release_preflight_gate_label` | Future release-preflight gate label. | Do not claim preflight pass. |
| `persistence_check_gate_label` | Future persistence-check gate label. | Do not claim persistence proof. |
| `host_firewall_gate_label` | Future firewall gate label. | Do not claim firewall proof. |
| `tls_certificate_gate_label` | Future TLS certificate gate label. | Do not record certificate values. |
| `rollback_path_gate_label` | Future rollback-path gate label. | Do not claim rollback verification. |
| `private_runtime_witness_gate_label` | Future private runtime witness gate label. | Do not record private witness values. |
| `dns_authority_gate_label` | Future DNS authority gate label. | Do not claim DNS authority. |
| `runtime_witness_closure_gate_label` | Future runtime witness closure gate label. | Do not claim witness closure. |
| `api_provisioning_stop_rule_label` | Future API provisioning stop-rule label. | Do not provision API runtime. |
| `dns_publication_stop_rule_label` | Future DNS publication stop-rule label. | Do not publish DNS. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve readiness or deployment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Upstream reporter command label | Record the field label only. | Do not execute the reporter. |
| Target gateway URL label | Record the field label only. | Do not record URL values. |
| Recovery witness gate label | Record the gate label only. | Do not claim recovery closure. |
| Production image gate label | Record the gate label only. | Do not record production image values. |
| Runtime host gate label | Record the gate label only. | Do not record host values. |
| Managed PostgreSQL gate label | Record the gate label only. | Do not record database values. |
| Schema application gate label | Record the gate label only. | Do not claim schema application. |
| Production secret store gate label | Record the gate label only. | Do not record or claim secrets. |
| Deploy-env gate label | Record the gate label only. | Do not claim deploy-env closure. |
| Release preflight gate label | Record the gate label only. | Do not claim preflight pass. |
| Persistence check gate label | Record the gate label only. | Do not claim persistence proof. |
| Host firewall gate label | Record the gate label only. | Do not claim firewall proof. |
| TLS certificate gate label | Record the gate label only. | Do not record certificate values. |
| Rollback path gate label | Record the gate label only. | Do not claim rollback verification. |
| Private runtime witness gate label | Record the gate label only. | Do not record private witness values. |
| DNS authority gate label | Record the gate label only. | Do not claim DNS authority. |
| Runtime witness closure gate label | Record the gate label only. | Do not claim witness closure. |
| API provisioning stop rule | Record the stop-rule label only. | Do not provision API runtime. |
| DNS publication stop rule | Record the stop-rule label only. | Do not select or publish DNS. |
| Operator reassessment gate | Record the gate label only. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as an upstream readiness gate-label rehearsal, not a
   readiness receipt.
2. Keep only public-safe gate labels and blocked-gate notes in Git.
3. Do not place target gateway URLs, hostnames, DNS targets, provider account
   identifiers, runtime host identifiers, database URLs, image tags, secret
   values, certificate values, private witness values, workflow run ids,
   artifact ids, approval references, personal data, payment details, private
   paths, or customer information in this witness.
4. Stop if the next step requires upstream reporter execution, require-ready
   pass, API provisioning, DNS target selection, DNS publication, repository
   variable binding, workflow dispatch, artifact publication, readiness
   promotion, customer access, payment, legal/business action, publication, or
   deployment.
5. Keep the rehearsal in `AwaitingEvidence` until an external operator-owned
   upstream readiness receipt, require-ready validation, DNS target-binding
   receipt, DNS resolution receipt, endpoint evidence receipt, and reassessment
   gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_deployment_upstream_api_gate_rehearsal_boundary.py
```

The validator checks that the deployment upstream API gate rehearsal witness:

1. keeps every upstream gate surface in `AwaitingEvidence`;
2. keeps upstream readiness, reporter execution, require-ready pass, target
   URL values, production dependency values, runtime host values, managed
   PostgreSQL values, schema application values, secret-store values,
   deploy-env values, release-preflight values, persistence-check values,
   firewall values, TLS certificate values, rollback-path values, private
   runtime witness values, DNS authority values, runtime witness closure,
   API provisioning, DNS publication, DNS target selection, repository
   variable binding, workflow dispatch, artifact publication, readiness,
   customer access, money, legal/business claims, publication, and deployment
   blocked;
3. allows only public-safe gate labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, secret/key material, and assignment shapes
   for upstream, target, gateway, production, runtime, database, schema,
   secret, deploy, release, persistence, firewall, TLS, rollback, witness,
   DNS, workflow, artifact, customer, money, legal/business, and deployment
   facts; and
5. rejects upstream readiness, require-ready, DNS, publication, workflow,
   artifact, readiness, approval, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Rehearse DNS target binding labels | [Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md) |
| Rehearse DNS resolution receipt labels | [Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md) |
| Rehearse endpoint reachability labels | [Foundation Gateway Endpoint Reachability Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md) |
| Rehearse endpoint evidence receipt fields | [Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: upstream API readiness not claimed, upstream reporter execution blocked, require-ready pass not claimed, target gateway URL value blocked, production dependency values blocked, runtime host values blocked, managed PostgreSQL values blocked, schema application values blocked, secret-store values blocked, deploy-env values blocked, release-preflight values blocked, persistence-check values blocked, firewall values blocked, TLS certificate values blocked, rollback-path values blocked, private runtime witness values blocked, DNS authority values blocked, runtime witness closure not claimed, API provisioning blocked, DNS publication blocked, DNS target selection blocked, repository-variable binding blocked, workflow dispatch blocked, artifact publication blocked, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all deployment upstream API gate rehearsal surfaces remain AwaitingEvidence
  Next action: validate this upstream gate-label rehearsal before any future DNS target selection or deployment witness publication work
