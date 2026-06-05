<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 gateway endpoint reachability questions without probing endpoints or recording endpoint evidence.
Governance scope: issue #330, gateway endpoint reachability rehearsal, local question labels, endpoint probe blocking, gateway URL blocking, response evidence blocking, witness collection blocking, public health declaration blocking, workflow blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md, examples/foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_gateway_endpoint_reachability_rehearsal_boundary.py.
Invariants: no endpoint probe, no gateway URL value, no HTTP status value, no response digest, no response body, no runtime witness payload, no runtime conformance payload, no production evidence payload, no capability evidence payload, no audit verification payload, no proof verification payload, no deployment witness collection, no public health declaration, no secret-presence claim, no workflow dispatch, no artifact publication, no operator approval claim, no readiness claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Gateway Endpoint Reachability Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** gateway endpoint reachability rehearsal means naming the
> local questions a future operator must answer before collecting endpoint
> evidence for issue #330. It does not probe endpoints, record gateway URL
> values, record HTTP status values, record response bodies, record response
> digests, collect deployment witnesses, declare public health, dispatch
> workflows, publish artifacts, approve readiness, open access, move money,
> make legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json)

Rule: Gateway endpoint reachability rehearsal is a local question map for a
later endpoint evidence receipt. It is not endpoint probing, not endpoint
proof, not deployment witness collection, not public health declaration, and
not deployment witness readiness.

No endpoint probe, gateway URL value, HTTP status value, response digest,
response body, runtime witness payload, runtime conformance payload, production
evidence payload, capability evidence payload, audit verification payload,
proof verification payload, deployment witness collection, public health
declaration, secret-presence claim, workflow dispatch, artifact publication,
operator approval claim, readiness claim, customer access, personal-data
collection, money movement, legal-clearance claim, company-formation claim,
patent claim, external publication, or deployment claim is permitted by this
boundary.

## What This Boundary Solves

After DNS resolution, issue #330 still needs endpoint evidence from the gateway
surface. In Foundation Mode, the safe work is not to probe those endpoints. The
safe work is to name the endpoint evidence questions and stop rules required
before a later operator can collect live evidence.

Use it when the question is:

1. Which endpoint reachability questions must a future operator answer?
2. Which endpoint evidence labels are safe to store publicly?
3. Which gateway URL, HTTP status, response digest, and response body values
   must stay out of Git?
4. Which deployment witness and public health gates still wait for live proof?
5. Which reassessment gate prevents rehearsal text from becoming endpoint proof?

## Current State

```text
gateway_endpoint_reachability_rehearsal_state=AwaitingEvidence
live_endpoint_probe_allowed=false
gateway_url_recorded=false
http_status_recorded=false
response_digest_recorded=false
response_body_recorded=false
runtime_witness_payload_recorded=false
runtime_conformance_payload_recorded=false
production_evidence_payload_recorded=false
capability_evidence_payload_recorded=false
audit_verification_payload_recorded=false
proof_verification_payload_recorded=false
deployment_witness_collected=false
public_health_declared=false
secret_presence_claimed=false
workflow_dispatch_allowed=false
artifact_publication_allowed=false
operator_approval_claimed=false
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

## Public-Safe Question Labels

These labels are questions only. They are not gateway URLs, endpoint
responses, HTTP status observations, response digests, response bodies, witness
payloads, conformance payloads, deployment witness identifiers, workflow run
identifiers, artifact identifiers, approval identifiers, or production health
evidence.

| Label | Later question | Boundary |
| --- | --- | --- |
| `health_endpoint_probe_question` | Which health endpoint evidence must be observed later? | Do not probe endpoints. |
| `gateway_witness_endpoint_question` | Which gateway witness evidence must be observed later? | Do not collect witness payloads. |
| `runtime_conformance_endpoint_question` | Which conformance evidence must be observed later? | Do not collect conformance payloads. |
| `endpoint_http_status_question` | Which HTTP status field belongs in a future receipt? | Do not record HTTP status values. |
| `endpoint_response_digest_question` | Which response digest field belongs in a future receipt? | Do not record response digests. |
| `endpoint_body_shape_question` | Which response body shape must be checked later? | Do not record response bodies. |
| `production_evidence_dependency_question` | Which production evidence gate remains blocked? | Do not collect production evidence. |
| `capability_evidence_dependency_question` | Which capability evidence gate remains blocked? | Do not collect capability evidence. |
| `audit_proof_dependency_question` | Which audit/proof gate remains blocked? | Do not collect audit or proof evidence. |
| `publication_stop_rule_question` | Which stop rule blocks publication? | Do not publish artifacts. |
| `operator_reassessment_gate` | Which later gate prevents promotion? | Do not approve reassessment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Health endpoint probe question | Record the question label. | Do not run endpoint probes. |
| Gateway witness endpoint question | Record the question label. | Do not collect gateway witness payloads. |
| Runtime conformance endpoint question | Record the question label. | Do not collect runtime conformance payloads. |
| Endpoint HTTP status question | Record the field label. | Do not record HTTP status values. |
| Endpoint response digest question | Record the field label. | Do not record response digests. |
| Endpoint body shape question | Record the field label. | Do not record response bodies. |
| Production evidence dependency question | Record the dependency label. | Do not collect production evidence payloads. |
| Capability evidence dependency question | Record the dependency label. | Do not collect capability evidence payloads. |
| Audit proof dependency question | Record the dependency label. | Do not collect audit or proof payloads. |
| Publication stop rule question | Record the stop-rule label. | Do not publish receipts or artifacts. |
| Operator reassessment gate | Record the gate label. | Do not approve endpoint proof or deployment. |

## Operator Procedure

1. Treat this boundary as a rehearsal map, not an endpoint evidence receipt.
2. Keep only public-safe question labels and blocked-gate labels in Git.
3. Do not place real gateway URLs, endpoint URLs, HTTP status values, response
   bodies, response digests, runtime witness payloads, runtime conformance
   payloads, production evidence payloads, capability evidence payloads, audit
   payloads, proof payloads, deployment witness ids, workflow run ids, artifact
   ids, approval ids, secret values, provider identifiers, account identifiers,
   personal data, payment details, private paths, or customer information in
   this witness.
4. Stop if the next step requires endpoint probing, gateway URL recording,
   HTTP status recording, response digest recording, response body recording,
   witness collection, conformance collection, production evidence collection,
   public health declaration, secret handling, workflow dispatch, artifact
   publication, operator approval, readiness promotion, customer access,
   payment, legal/business action, publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until an external operator thread,
   DNS resolution receipt, endpoint evidence receipt, deployment witness
   receipt, public health declaration receipt, and reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_gateway_endpoint_reachability_rehearsal_boundary.py
```

The validator checks that the gateway endpoint reachability rehearsal witness:

1. keeps every rehearsal surface in `AwaitingEvidence`;
2. keeps endpoint probes, gateway URL values, HTTP status values, response
   digests, response bodies, runtime witness payloads, runtime conformance
   payloads, production evidence payloads, capability evidence payloads, audit
   proof payloads, deployment witness collection, public health declaration,
   secret presence, workflow dispatch, artifact publication, operator approval,
   readiness, customer access, money, legal/business claims, publication, and
   deployment blocked;
3. allows only public-safe question labels and blocked-gate notes;
4. rejects live URLs, host-looking values, IP-looking values, timestamps,
   private paths, email-like identifiers, response evidence values, and
   assignment shapes for endpoints, URLs, status, bodies, digests, witnesses,
   conformance, production evidence, capability evidence, audit, proof,
   workflows, artifacts, approvals, customers, money, legal/business facts, and
   deployment facts; and
5. rejects endpoint, witness, conformance, public health, readiness, approval,
   publication, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse DNS resolution receipt labels | [Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md) |
| Rehearse DNS target binding without publication | [Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Name deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Name evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: endpoint probe blocked, gateway URL value blocked, HTTP status values blocked, response digests blocked, response bodies blocked, witness payloads blocked, conformance payloads blocked, production/capability/audit/proof payloads blocked, deployment witness collection blocked, public health declaration blocked, secret presence not claimed, workflow dispatch blocked, artifact publication blocked, operator approval not claimed, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all gateway endpoint reachability rehearsal surfaces remain AwaitingEvidence
  Next action: validate this rehearsal boundary before any future endpoint evidence receipt collection or deployment witness work
