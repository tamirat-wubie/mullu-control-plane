<!--
Purpose: define the Foundation Mode boundary for rehearsing the future issue #330 gateway endpoint evidence receipt shape without collecting endpoint evidence or recording runtime values.
Governance scope: issue #330, gateway endpoint evidence receipt rehearsal, local receipt field labels, endpoint probe blocking, endpoint URL blocking, response evidence blocking, timestamp blocking, collector identity blocking, evidence-ledger append blocking, public health declaration blocking, workflow blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md, examples/foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary.py.
Invariants: no endpoint probe, no gateway URL value, no endpoint URL value, no HTTP status value, no response digest value, no response body value, no collection timestamp value, no collector identity value, no runtime witness payload, no runtime conformance payload, no production evidence payload, no capability evidence payload, no audit verification payload, no proof verification payload, no evidence-ledger append, no deployment witness collection, no public health declaration, no secret-presence claim, no workflow dispatch, no artifact publication, no operator approval claim, no readiness claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** gateway endpoint evidence receipt rehearsal means naming the
> future receipt fields a later operator must fill after approved external
> sensing. It does not probe endpoints, record gateway or endpoint URL values,
> record HTTP status values, record response bodies, record response digests,
> record collection timestamps, record collector identities, append evidence to
> a ledger, publish artifacts, approve readiness, open access, move money, make
> legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json)

Rule: Gateway endpoint evidence receipt rehearsal is a local receipt field
map for a future operator thread. It is not endpoint evidence, not endpoint
proof, not evidence-ledger append, not deployment witness collection, not
public health declaration, and not deployment readiness.

No endpoint probe, gateway URL value, endpoint URL value, HTTP status value,
response digest value, response body value, collection timestamp value,
collector identity value, runtime witness payload, runtime conformance
payload, production evidence payload, capability evidence payload, audit
verification payload, proof verification payload, evidence-ledger append,
deployment witness collection, public health declaration, secret-presence
claim, workflow dispatch, artifact publication, operator approval claim,
readiness claim, customer access, personal-data collection, money movement,
legal-clearance claim, company-formation claim, patent claim, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The endpoint reachability boundary names the questions. This boundary names
the future receipt fields so later endpoint evidence can be collected in a
governed container instead of loose notes. In Foundation Mode, the receipt
shape is safe; the runtime values are not safe to store.

Use it when the question is:

1. Which receipt field labels must exist before endpoint evidence collection?
2. Which response fields must stay empty until external sensing is approved?
3. Which timestamp, collector, and validation-result fields are sensitive?
4. Which evidence-ledger route remains blocked until a real receipt exists?
5. Which reassessment gate prevents receipt rehearsal from becoming proof?

## Current State

```text
gateway_endpoint_evidence_receipt_rehearsal_state=AwaitingEvidence
endpoint_probe_allowed=false
gateway_url_value_allowed=false
endpoint_url_value_allowed=false
http_status_value_allowed=false
response_digest_value_allowed=false
response_body_value_allowed=false
collection_timestamp_value_allowed=false
collector_identity_value_allowed=false
runtime_witness_payload_allowed=false
runtime_conformance_payload_allowed=false
production_evidence_payload_allowed=false
capability_evidence_payload_allowed=false
audit_verification_payload_allowed=false
proof_verification_payload_allowed=false
evidence_ledger_append_allowed=false
deployment_witness_collection_allowed=false
public_health_declaration_allowed=false
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

## Public-Safe Receipt Field Labels

These labels are receipt fields only. They are not endpoint URLs, response
observations, response bodies, response digests, timestamps, collector
identities, validation results, evidence-ledger entries, approval ids,
workflow run ids, artifact ids, deployment witness ids, or production health
evidence.

| Label | Later receipt field | Boundary |
| --- | --- | --- |
| `endpoint_evidence_receipt_id_label` | Future receipt identity label. | Do not assign a receipt id. |
| `endpoint_evidence_source_boundary_label` | Future source-boundary label. | Do not claim source proof. |
| `health_endpoint_observation_slot` | Future health observation slot. | Do not record observations. |
| `gateway_witness_observation_slot` | Future gateway witness observation slot. | Do not record witness payloads. |
| `runtime_conformance_observation_slot` | Future conformance observation slot. | Do not record conformance payloads. |
| `endpoint_http_status_slot` | Future HTTP status slot. | Do not record HTTP status values. |
| `endpoint_response_digest_slot` | Future response digest slot. | Do not record response digests. |
| `endpoint_body_schema_slot` | Future body-shape validation slot. | Do not record response bodies. |
| `endpoint_collection_time_slot` | Future collection time slot. | Do not record timestamps. |
| `endpoint_collector_identity_slot` | Future collector identity slot. | Do not record identities. |
| `endpoint_redaction_note_slot` | Future redaction note slot. | Do not store sensitive values. |
| `endpoint_validation_result_slot` | Future validation-result slot. | Do not claim validation pass. |
| `endpoint_evidence_ledger_route_slot` | Future evidence-ledger route slot. | Do not append to the ledger. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve proof or deployment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Endpoint evidence receipt id label | Record the label only. | Do not create a receipt id. |
| Source boundary label | Record the label only. | Do not claim source proof. |
| Health endpoint observation slot | Record the slot label. | Do not record observations. |
| Gateway witness observation slot | Record the slot label. | Do not record witness payloads. |
| Runtime conformance observation slot | Record the slot label. | Do not record conformance payloads. |
| Endpoint HTTP status slot | Record the slot label. | Do not record HTTP status values. |
| Endpoint response digest slot | Record the slot label. | Do not record response digests. |
| Endpoint body schema slot | Record the slot label. | Do not record response bodies. |
| Endpoint collection time slot | Record the slot label. | Do not record timestamps. |
| Endpoint collector identity slot | Record the slot label. | Do not record identities. |
| Endpoint redaction note slot | Record the slot label. | Do not store sensitive values. |
| Endpoint validation result slot | Record the slot label. | Do not claim validation pass. |
| Endpoint evidence ledger route slot | Record the route label. | Do not append evidence. |
| Operator reassessment gate | Record the gate label. | Do not approve endpoint proof or deployment. |

## Operator Procedure

1. Treat this boundary as a receipt-shape rehearsal, not an evidence receipt.
2. Keep only public-safe field labels and blocked-gate notes in Git.
3. Do not place real gateway URLs, endpoint URLs, HTTP status values, response
   bodies, response digests, timestamps, collector identities, runtime witness
   payloads, runtime conformance payloads, production evidence payloads,
   capability evidence payloads, audit payloads, proof payloads, deployment
   witness ids, workflow run ids, artifact ids, approval ids, secret values,
   provider identifiers, account identifiers, personal data, payment details,
   private paths, or customer information in this witness.
4. Stop if the next step requires endpoint probing, gateway URL recording,
   endpoint URL recording, HTTP status recording, response digest recording,
   response body recording, timestamp recording, collector identity recording,
   witness collection, conformance collection, production evidence collection,
   public health declaration, secret handling, workflow dispatch, artifact
   publication, evidence-ledger append, operator approval, readiness promotion,
   customer access, payment, legal/business action, publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until an external operator thread,
   DNS resolution receipt, endpoint evidence receipt, deployment witness
   receipt, public health declaration receipt, evidence-ledger append receipt,
   and reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary.py
```

The validator checks that the gateway endpoint evidence receipt rehearsal
witness:

1. keeps every receipt field surface in `AwaitingEvidence`;
2. keeps endpoint probes, gateway URL values, endpoint URL values, HTTP status
   values, response digests, response bodies, timestamps, collector
   identities, runtime witness payloads, runtime conformance payloads,
   production evidence payloads, capability evidence payloads, audit proof
   payloads, evidence-ledger append, deployment witness collection, public
   health declaration, secret presence, workflow dispatch, artifact
   publication, operator approval, readiness, customer access, money,
   legal/business claims, publication, and deployment blocked;
3. allows only public-safe receipt field labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, response evidence values, and assignment
   shapes for endpoints, URLs, statuses, bodies, digests, witnesses,
   conformance, production evidence, capability evidence, audit, proof,
   ledgers, workflows, artifacts, approvals, customers, money, legal/business
   facts, and deployment facts; and
5. rejects endpoint evidence, receipt publication, public health, readiness,
   approval, ledger append, publication, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse endpoint reachability labels | [Foundation Gateway Endpoint Reachability Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Name deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Name evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Route future evidence without closure claims | [Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: endpoint probe blocked, gateway URL value blocked, endpoint URL value blocked, HTTP status values blocked, response digests blocked, response bodies blocked, timestamps blocked, collector identities blocked, witness payloads blocked, conformance payloads blocked, production/capability/audit/proof payloads blocked, evidence-ledger append blocked, deployment witness collection blocked, public health declaration blocked, secret presence not claimed, workflow dispatch blocked, artifact publication blocked, operator approval not claimed, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all gateway endpoint evidence receipt rehearsal surfaces remain AwaitingEvidence
  Next action: validate this receipt-shape rehearsal boundary before any future endpoint evidence receipt collection or deployment witness work
