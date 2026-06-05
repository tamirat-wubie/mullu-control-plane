<!--
Purpose: define the Foundation Mode boundary for rehearsing future external evidence acceptance decisions without collecting, accepting, rejecting, publishing, or promoting live evidence.
Governance scope: issue #330, external evidence acceptance rehearsal, public-safe evidence labels, redaction gates, freshness gates, chain-of-custody gates, schema-validation gates, replay gates, ledger-append blocking, readiness-promotion blocking, publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md, examples/foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_external_evidence_acceptance_rehearsal_boundary.py.
Invariants: no external evidence collection, no source-authority verification claim, no evidence-owner verification claim, no redaction pass claim, no freshness pass claim, no chain-of-custody verification claim, no schema-validation pass claim, no contradiction-check pass claim, no replay pass claim, no acceptance decision, no rejection decision, no ledger append, no readiness promotion, no API provisioning, no DNS publication, no workflow dispatch, no artifact publication, no public health declaration, no deployment witness publication, no customer access, no personal-data collection, no money movement, no legal/company/patent claim, no external publication, and no deployment claim.
-->

# Foundation External Evidence Acceptance Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** external evidence acceptance rehearsal means naming the
> future gates that will decide whether operator-owned evidence is acceptable,
> stale, overexposed, contradictory, replayable, ledger-safe, or promotion-safe.
> It does not collect evidence, verify sources, record private values, accept or
> reject evidence, append evidence to a ledger, promote readiness, publish
> artifacts, declare public health, publish deployment witnesses, open access,
> move money, make legal/business claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json)

Rule: External evidence acceptance rehearsal is a local gate-label map for
future operator-owned evidence review. It is not evidence collection, not source
authority proof, not redaction proof, not freshness proof, not
chain-of-custody proof, not schema-validation proof, not replay proof, not
ledger append permission, not readiness promotion, and not deployment readiness.

No external evidence collection, source-authority verification claim,
evidence-owner verification claim, redaction pass claim, freshness pass claim,
chain-of-custody verification claim, schema-validation pass claim,
contradiction-check pass claim, replay pass claim, acceptance decision,
rejection decision, ledger append, readiness promotion, API provisioning, DNS
publication, workflow dispatch, artifact publication, public health
declaration, deployment witness publication, customer access, personal-data
collection, money movement, legal/company/patent claim, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 remains `AwaitingEvidence` because the missing pieces are external
operator evidence and live runtime/DNS publication. Other Foundation Mode
boundaries can name the future evidence slots. This boundary adds the next
local prerequisite: the review gates that will keep future evidence from being
accepted too early or promoted without proof.

Use it when the question is:

1. What must be checked before a future external evidence receipt can be
   accepted?
2. Which checks are only labels today, not real validation results?
3. How do we keep stale, private, contradictory, or overexposed evidence from
   entering public artifacts?
4. Which gates prevent evidence acceptance from becoming readiness promotion?
5. Which reassessment step keeps this work local until real evidence exists?

## Current State

```text
external_evidence_acceptance_rehearsal_state=AwaitingEvidence
external_evidence_collected=false
source_authority_verified=false
evidence_owner_verified=false
redaction_pass_claimed=false
freshness_pass_claimed=false
chain_of_custody_verified=false
schema_validation_pass_claimed=false
contradiction_check_pass_claimed=false
replay_pass_claimed=false
acceptance_decision_recorded=false
rejection_decision_recorded=false
ledger_append_allowed=false
readiness_promotion_allowed=false
api_provisioning_allowed=false
dns_publication_allowed=false
workflow_dispatch_allowed=false
artifact_publication_allowed=false
public_health_declaration_allowed=false
deployment_witness_publication_allowed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Acceptance Labels

These labels are review gates only. They are not evidence receipts, URLs,
hostnames, IP addresses, runtime values, database values, secret names or
values, certificate values, workflow run ids, artifact ids, approval
references, timestamps, hashes, private paths, customer data, or proof that any
external evidence is acceptable.

| Label | Later review class | Boundary |
| --- | --- | --- |
| `evidence_source_boundary_label` | Future source-boundary review label. | Do not verify source authority. |
| `evidence_classification_label` | Future evidence-classification label. | Do not classify live evidence. |
| `evidence_owner_label` | Future owner review label. | Do not verify evidence ownership. |
| `evidence_redaction_gate_label` | Future redaction gate label. | Do not claim redaction pass. |
| `evidence_value_absence_gate_label` | Future value-exposure gate label. | Do not record live values. |
| `evidence_freshness_gate_label` | Future freshness gate label. | Do not claim freshness pass. |
| `evidence_chain_of_custody_label` | Future custody gate label. | Do not claim custody proof. |
| `evidence_schema_validation_label` | Future schema-validation gate label. | Do not claim schema pass. |
| `evidence_contradiction_check_label` | Future contradiction-check label. | Do not claim contradiction clearance. |
| `evidence_replay_requirement_label` | Future replay gate label. | Do not claim replay pass. |
| `evidence_rejection_reason_label` | Future rejection-reason label. | Do not record a final rejection decision. |
| `evidence_acceptance_decision_label` | Future acceptance-decision label. | Do not record an acceptance decision. |
| `ledger_append_gate_label` | Future evidence-ledger append gate. | Do not append evidence. |
| `readiness_promotion_gate_label` | Future readiness-promotion gate. | Do not promote readiness. |
| `operator_reassessment_gate` | Future reassessment gate. | Do not approve readiness or deployment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Source boundary | Record the review label only. | Do not verify source authority. |
| Evidence classification | Record the review label only. | Do not classify live evidence. |
| Evidence owner | Record the review label only. | Do not verify ownership. |
| Redaction gate | Record the gate label only. | Do not claim redaction pass. |
| Value absence gate | Record the gate label only. | Do not record live values. |
| Freshness gate | Record the gate label only. | Do not claim freshness pass. |
| Chain of custody | Record the gate label only. | Do not claim custody proof. |
| Schema validation | Record the gate label only. | Do not claim schema pass. |
| Contradiction check | Record the gate label only. | Do not claim contradiction clearance. |
| Replay requirement | Record the gate label only. | Do not claim replay pass. |
| Rejection reason | Record the label only. | Do not record a final rejection decision. |
| Acceptance decision | Record the label only. | Do not record an acceptance decision. |
| Ledger append | Record the gate label only. | Do not append evidence. |
| Readiness promotion | Record the gate label only. | Do not promote readiness. |
| Operator reassessment | Record the gate label only. | Do not approve readiness or deployment. |

## Operator Procedure

1. Treat this boundary as a local acceptance-gate rehearsal, not an evidence
   review record.
2. Keep only public-safe labels and blocked-gate notes in Git.
3. Do not place evidence receipts, URLs, hostnames, IP addresses, runtime
   values, database values, secret names or values, certificate values,
   workflow run ids, artifact ids, approval references, timestamps, hashes,
   private paths, personal data, customer data, payment details, or provider
   account details in this witness.
4. Stop if the next step requires collecting evidence, verifying source
   authority, validating real receipts, appending to an evidence ledger,
   promoting readiness, provisioning runtime, publishing DNS, dispatching
   workflows, publishing artifacts, declaring public health, publishing a
   deployment witness, opening customer access, payment, legal/business action,
   external publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until real operator-owned evidence
   receipts exist and the evidence acceptance, ledger routing, upstream API,
   DNS, endpoint, deployment witness, and public health gates can each pass
   their own validators.

## Validation

Run:

```powershell
python scripts/validate_foundation_external_evidence_acceptance_rehearsal_boundary.py
```

The validator checks that the external evidence acceptance rehearsal witness:

1. keeps every acceptance surface in `AwaitingEvidence`;
2. keeps external evidence collection, source verification, owner verification,
   redaction, freshness, custody, schema validation, contradiction checks,
   replay, acceptance decisions, rejection decisions, ledger append, readiness
   promotion, API provisioning, DNS publication, workflow dispatch, artifact
   publication, public health declaration, deployment witness publication,
   customer access, money, legal/business claims, publication, and deployment
   blocked;
3. allows only public-safe gate labels and blocked-gate notes;
4. rejects URLs, host-looking values, IP-looking values, timestamps, private
   paths, email-like identifiers, secret/key material, hash-like values, and
   assignment shapes for evidence facts; and
5. rejects evidence-acceptance, validation, ledger, readiness, public health,
   witness-publication, approval, publication, and deployment promotion
   phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse production dependency labels | [Foundation Production Dependency Evidence Rehearsal Boundary](FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md) |
| Rehearse upstream API readiness gates | [Foundation Deployment Upstream API Gate Rehearsal Boundary](FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md) |
| Rehearse evidence-ledger routing | [Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md) |
| Rehearse public health declaration labels | [Foundation Public Health Declaration Rehearsal Boundary](FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: external evidence collection blocked, source authority not verified, evidence owner not verified, redaction pass not claimed, freshness pass not claimed, custody not verified, schema pass not claimed, contradiction check pass not claimed, replay pass not claimed, acceptance decision not recorded, rejection decision not recorded, ledger append blocked, readiness promotion blocked, API provisioning blocked, DNS publication blocked, workflow dispatch blocked, artifact publication blocked, public health declaration blocked, deployment witness publication blocked, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all external evidence acceptance surfaces remain AwaitingEvidence
  Next action: validate this acceptance-gate rehearsal before any future evidence ingestion, ledger append, readiness promotion, or deployment witness work
