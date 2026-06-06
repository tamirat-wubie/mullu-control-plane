<!--
Purpose: define the Foundation Mode boundary for deferring runtime witness creation, verification, publication, and trust claims until deployment evidence exists.
Governance scope: issue #330, runtime witness creation blocking, signature verification blocking, endpoint probe blocking, runtime conformance blocking, deployment witness collection blocking, evidence-ledger append blocking, readiness blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md, examples/foundation_runtime_witness_deferral_witness.awaiting_evidence.json, scripts/validate_foundation_runtime_witness_deferral_boundary.py.
Invariants: no runtime witness creation, no runtime witness secret binding, no endpoint probe, no runtime witness payload recording, no runtime witness signature verification, no runtime witness publication, no runtime conformance claim, no deployment witness collection, no evidence-ledger append, no readiness claim, no customer access, no personal-data collection, no money movement, no legal/company/patent claim, no external publication, and no deployment claim.
-->

# Foundation Runtime Witness Deferral Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** runtime witness deferral means recording why the runtime
> witness is not created, probed, signed, published, trusted, or used as
> readiness evidence in Foundation Mode. It does not provision secrets, probe
> endpoints, record witness payloads, verify signatures, collect deployment
> witnesses, append evidence ledgers, open access, move money, make
> legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_runtime_witness_deferral_witness.awaiting_evidence.json`](../examples/foundation_runtime_witness_deferral_witness.awaiting_evidence.json)

Rule: Runtime witness deferral is a local stop-rule packet for future runtime
witness proof. It is not a runtime witness, not a signature check, not endpoint
evidence, not runtime conformance, not a deployment witness, and not readiness
promotion.

No runtime witness creation, runtime witness secret binding, endpoint probe,
runtime witness payload recording, runtime witness signature verification,
runtime witness publication, runtime conformance claim, deployment witness
collection, evidence-ledger append, readiness claim, customer access,
personal-data collection, money movement, legal/company/patent claim, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 cannot close until a later environment can expose a valid runtime
witness and conformance evidence. In Foundation Mode, the safe local action is
to record the deferral gates, not to create live witness material or trust
placeholder evidence.

Use it when the question is:

1. Why is there no runtime witness readiness claim yet?
2. Which runtime witness facts must stay out of Git and public docs?
3. Which future checks are only labels today?
4. Which gates prevent placeholder evidence from becoming trusted proof?
5. Which reassessment step must happen before runtime witness collection?

## Current State

```text
runtime_witness_deferral_state=AwaitingEvidence
runtime_witness_created=false
runtime_witness_secret_bound=false
runtime_witness_endpoint_probe_allowed=false
runtime_witness_payload_recorded=false
runtime_witness_signature_verified=false
runtime_witness_publication_allowed=false
runtime_conformance_claimed=false
deployment_witness_collection_allowed=false
evidence_ledger_append_allowed=false
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

## Public-Safe Deferral Labels

These labels are stop-rule gates only. They are not endpoint URLs, witness
payloads, signatures, secret identifiers, run identifiers, approval records,
timestamps, hashes, or evidence receipts.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `runtime_witness_creation_gate` | Future witness creation gate. | Do not create or claim a runtime witness. |
| `runtime_witness_secret_binding_gate` | Future secret binding gate. | Do not bind or claim runtime witness secrets. |
| `runtime_witness_endpoint_probe_gate` | Future endpoint probe gate. | Do not probe endpoints. |
| `runtime_witness_payload_value_gate` | Future payload value gate. | Do not record witness payloads. |
| `runtime_witness_signature_gate` | Future signature verification gate. | Do not claim signature verification. |
| `runtime_witness_publication_gate` | Future publication gate. | Do not publish witness material. |
| `runtime_conformance_gate` | Future runtime conformance gate. | Do not claim conformance. |
| `deployment_witness_collection_gate` | Future deployment witness collection gate. | Do not collect deployment witnesses. |
| `evidence_ledger_routing_gate` | Future evidence-ledger routing gate. | Do not append evidence. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve readiness or deployment. |

## Deferral Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Runtime witness creation | Record the stop-rule label. | Do not create or claim witness existence. |
| Secret binding | Record the stop-rule label. | Do not bind or claim secret readiness. |
| Endpoint probing | Record the stop-rule label. | Do not probe or record endpoints. |
| Witness payload | Record the stop-rule label. | Do not record payload values. |
| Signature verification | Record the stop-rule label. | Do not claim signature verification. |
| Witness publication | Record the stop-rule label. | Do not publish witness material. |
| Runtime conformance | Record the stop-rule label. | Do not claim conformance. |
| Deployment witness collection | Record the stop-rule label. | Do not collect deployment witnesses. |
| Evidence ledger routing | Record the stop-rule label. | Do not append evidence. |
| Operator reassessment | Record the stop-rule label. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as a deferral packet, not as a runtime witness.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not place endpoint URLs, host values, witness payloads, signatures,
   secret names, secret values, account identifiers, provider identifiers, run
   ids, artifact ids, approval ids, timestamps, hashes, personal data, customer
   data, payment details, or private paths in this witness.
4. Stop if the next step requires endpoint probing, witness creation, signature
   verification, secret binding, conformance proof, deployment witness
   collection, evidence-ledger append, customer access, payment,
   legal/business action, external publication, or deployment.
5. Keep the deferral in `AwaitingEvidence` until an operator-owned runtime
   environment, secret handoff receipt, endpoint evidence, conformance receipt,
   deployment witness, and reassessment gate can each pass their own validators.

## Validation

Run:

```powershell
python scripts/validate_foundation_runtime_witness_deferral_boundary.py
```

The validator checks that the runtime witness deferral witness:

1. keeps every deferral surface in `AwaitingEvidence`;
2. keeps witness creation, secret binding, endpoint probing, payload recording,
   signature verification, witness publication, runtime conformance,
   deployment witness collection, evidence-ledger append, readiness, customer
   access, money, legal/business claims, publication, and deployment blocked;
3. allows only public-safe deferral labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, secret/key material, hash-like values, and
   assignment shapes for runtime witness facts; and
5. rejects witness-created, signature-verified, endpoint-probed, conformance,
   evidence-ledger, readiness, publication, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse runtime secret handoff labels | [Foundation Runtime Secret Handoff Rehearsal Boundary](FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md) |
| Rehearse production dependency labels | [Foundation Production Dependency Evidence Rehearsal Boundary](FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md) |
| Prepare deployment witness evidence slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: runtime witness creation blocked, runtime witness secret binding blocked, endpoint probing blocked, witness payload recording blocked, signature verification blocked, witness publication blocked, runtime conformance blocked, deployment witness collection blocked, evidence-ledger append blocked, readiness not claimed, customer access blocked, personal-data collection blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all runtime witness surfaces remain AwaitingEvidence
  Next action: validate this runtime witness deferral before any future runtime witness, conformance, deployment witness, or public health work
