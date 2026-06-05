<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 production dependency evidence labels without collecting live infrastructure evidence.
Governance scope: issue #330, production dependency evidence rehearsal, local evidence labels, recovery witness blocking, runtime host value blocking, managed database value blocking, secret-store value blocking, TLS value blocking, rollback verification blocking, DNS authority blocking, workflow blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md, examples/foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_production_dependency_evidence_rehearsal_boundary.py.
Invariants: no recovery witness closure claim, no production image value, no runtime host value, no managed PostgreSQL value, no schema-application claim, no secret-store value, no deploy-env value, no release-preflight pass claim, no persistence-check pass claim, no firewall pass claim, no TLS certificate value, no rollback-path verification claim, no private runtime witness value, no DNS authority verification claim, no runtime witness registry closure claim, no external evidence collection, no API provisioning, no DNS publication, no DNS target selection, no repository-variable binding, no workflow dispatch, no artifact publication, no readiness claim, no customer access, no personal-data collection, no money movement, no legal/company/patent claim, no external publication, and no deployment claim.
-->

# Foundation Production Dependency Evidence Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** production dependency evidence rehearsal means naming the
> future evidence slots for the external/manual blockers that must close before
> upstream API readiness, DNS publication, deployment witness collection, or
> public health declaration. It does not collect infrastructure evidence, record
> values, provision services, bind variables, dispatch workflows, publish
> artifacts, open access, move money, make legal/business claims, publish
> externally, or deploy.

Witness packet: [`../examples/foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json)

Rule: Production dependency evidence rehearsal is a local evidence-label map
for future operator-owned dependency receipts. It is not dependency readiness,
not recovery closure, not production image proof, not runtime host proof, not
database proof, not secret-store proof, not TLS proof, not rollback proof, not
DNS authority proof, and not deployment readiness.

No recovery witness closure claim, production image value, runtime host value,
managed PostgreSQL value, schema-application claim, secret-store value,
deploy-env value, release-preflight pass claim, persistence-check pass claim,
firewall pass claim, TLS certificate value, rollback-path verification claim,
private runtime witness value, DNS authority verification claim, runtime witness
registry closure claim, external evidence collection, API provisioning, DNS
publication, DNS target selection, repository-variable binding, workflow
dispatch, artifact publication, readiness claim, customer access, personal-data
collection, money movement, legal/company/patent claim, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 remains blocked on external/manual evidence before the system can
publish DNS, collect deployment witnesses, or declare public health. Foundation
Mode must not fabricate that evidence. This boundary gives the solo operator a
public-safe checklist shape for those future receipts without asking for live
values.

Use it when the question is:

1. Which production dependency evidence classes remain external/manual?
2. Which values must stay out of Git and out of public artifacts?
3. Which future receipts must exist before upstream readiness can close?
4. Which stop rules prevent evidence labels from becoming readiness proof?
5. Which reassessment gate keeps this work local until real evidence exists?

## Current State

```text
production_dependency_evidence_rehearsal_state=AwaitingEvidence
recovery_witness_closed_claimed=false
production_image_value_recorded=false
runtime_host_value_recorded=false
managed_postgres_value_recorded=false
schema_application_claimed=false
secret_store_value_recorded=false
deploy_env_value_recorded=false
release_preflight_pass_claimed=false
persistence_check_pass_claimed=false
host_firewall_pass_claimed=false
tls_certificate_value_recorded=false
rollback_path_verified=false
private_runtime_witness_value_recorded=false
dns_authority_verified=false
runtime_witness_registry_closure_claimed=false
external_evidence_collected=false
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

## Public-Safe Evidence Labels

These labels are receipt fields only. They are not hostnames, image tags,
database URLs, schema migration ids, secret names or values, environment names,
preflight pass ids, persistence results, firewall rules, certificate values,
rollback paths, private witness material, DNS authority records, workflow runs,
artifacts, approvals, or evidence that a production dependency exists.

| Label | Later evidence class | Boundary |
| --- | --- | --- |
| `recovery_witness_gate_label` | Future recovery witness closure label. | Do not claim recovery closure. |
| `production_image_evidence_label` | Future production image evidence label. | Do not record image values. |
| `runtime_host_evidence_label` | Future runtime host evidence label. | Do not record host values. |
| `managed_postgres_evidence_label` | Future managed PostgreSQL evidence label. | Do not record database values. |
| `schema_application_evidence_label` | Future schema-application evidence label. | Do not claim schema application. |
| `production_secret_store_evidence_label` | Future secret-store evidence label. | Do not record or claim secrets. |
| `deploy_env_evidence_label` | Future deploy-env evidence label. | Do not record environment values. |
| `release_preflight_evidence_label` | Future release-preflight evidence label. | Do not claim preflight pass. |
| `persistence_check_evidence_label` | Future persistence-check evidence label. | Do not claim persistence proof. |
| `host_firewall_evidence_label` | Future firewall evidence label. | Do not claim firewall proof. |
| `tls_certificate_evidence_label` | Future TLS certificate evidence label. | Do not record certificate values. |
| `rollback_path_evidence_label` | Future rollback-path evidence label. | Do not claim rollback verification. |
| `private_runtime_witness_evidence_label` | Future private runtime witness label. | Do not record private witness material. |
| `dns_authority_evidence_label` | Future DNS authority evidence label. | Do not claim DNS authority. |
| `runtime_witness_registry_closure_label` | Future runtime witness registry closure label. | Do not claim registry closure. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve readiness or deployment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Recovery witness closure | Record the evidence label only. | Do not claim recovery closure. |
| Production image | Record the evidence label only. | Do not record image values. |
| Runtime host | Record the evidence label only. | Do not record host values. |
| Managed PostgreSQL | Record the evidence label only. | Do not record database values. |
| Schema application | Record the evidence label only. | Do not claim schema application. |
| Production secret store | Record the evidence label only. | Do not record or claim secrets. |
| Deploy environment | Record the evidence label only. | Do not record environment values. |
| Release preflight | Record the evidence label only. | Do not claim preflight pass. |
| Persistence check | Record the evidence label only. | Do not claim persistence proof. |
| Host firewall | Record the evidence label only. | Do not claim firewall proof. |
| TLS certificate | Record the evidence label only. | Do not record certificate values. |
| Rollback path | Record the evidence label only. | Do not claim rollback verification. |
| Private runtime witness | Record the evidence label only. | Do not record private witness material. |
| DNS authority | Record the evidence label only. | Do not claim DNS authority. |
| Runtime witness registry closure | Record the evidence label only. | Do not claim registry closure. |
| Operator reassessment | Record the gate label only. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as a production dependency evidence-label rehearsal, not
   a dependency evidence receipt.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not place hostnames, IP addresses, image tags, database URLs, schema
   migration ids, secret names or values, environment values, preflight ids,
   persistence results, firewall rules, certificate values, rollback paths,
   private witness values, DNS account data, workflow run ids, artifact ids,
   approval references, personal data, payment details, private paths, or
   customer information in this witness.
4. Stop if the next step requires collecting evidence, provisioning runtime,
   selecting or publishing DNS, binding repository variables, dispatching
   workflows, publishing artifacts, claiming readiness, opening customer access,
   payment, legal/business action, external publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until real operator-owned evidence
   receipts exist and the upstream API gate, DNS target binding, DNS resolution,
   endpoint reachability, endpoint evidence receipt, deployment witness, and
   public health declaration gates can each pass their own validators.

## Validation

Run:

```powershell
python scripts/validate_foundation_production_dependency_evidence_rehearsal_boundary.py
```

The validator checks that the production dependency evidence rehearsal witness:

1. keeps every production dependency surface in `AwaitingEvidence`;
2. keeps recovery closure, production image values, runtime host values, managed
   PostgreSQL values, schema-application claims, secret-store values, deploy-env
   values, release-preflight pass claims, persistence-check pass claims,
   firewall pass claims, TLS certificate values, rollback-path verification,
   private runtime witness values, DNS authority verification, registry closure,
   external evidence collection, API provisioning, DNS publication, DNS target
   selection, repository-variable binding, workflow dispatch, artifact
   publication, readiness, customer access, money, legal/business claims,
   publication, and deployment blocked;
3. allows only public-safe evidence labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, secret/key material, and assignment shapes for
   production dependency evidence facts; and
5. rejects production dependency, recovery, runtime, database, secret-store,
   TLS, rollback, DNS, readiness, approval, publication, and deployment
   promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse upstream API readiness gates | [Foundation Deployment Upstream API Gate Rehearsal Boundary](FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md) |
| Rehearse DNS target binding labels | [Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md) |
| Rehearse DNS resolution receipt labels | [Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md) |
| Rehearse endpoint reachability labels | [Foundation Gateway Endpoint Reachability Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: recovery witness closure not claimed, production image value blocked, runtime host value blocked, managed PostgreSQL value blocked, schema application not claimed, secret-store value blocked, deploy-env value blocked, release-preflight pass not claimed, persistence-check pass not claimed, firewall pass not claimed, TLS certificate value blocked, rollback-path verification not claimed, private runtime witness value blocked, DNS authority not verified, runtime witness registry closure not claimed, external evidence collection blocked, API provisioning blocked, DNS publication blocked, DNS target selection blocked, repository-variable binding blocked, workflow dispatch blocked, artifact publication blocked, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all production dependency evidence surfaces remain AwaitingEvidence
  Next action: validate this production dependency evidence-label rehearsal before any future upstream API readiness, DNS target selection, or deployment witness work
