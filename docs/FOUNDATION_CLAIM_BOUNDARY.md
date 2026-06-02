<!--
Purpose: define the Foundation Mode claim boundary before any production-health, endpoint-readiness, customer-readiness, pilot-readiness, legal-clearance, commercial-readiness, public-launch, compliance-certification, external-publication, or deployment claim.
Governance scope: repository proof claims, public-copy claims, runtime-proof claims, legal/business claims, customer/pilot claims, deployment claims, evidence-promotion questions, private-value exclusion, and claim-promotion blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/CURRENT_READINESS_SNAPSHOT.md, docs/PUBLIC_NAMING_READINESS.md, examples/foundation_claim_boundary_witness.awaiting_evidence.json, scripts/validate_foundation_claim_boundary.py.
Invariants: no production-health claim, no endpoint-readiness claim, no customer-readiness claim, no pilot-readiness claim, no legal-clearance claim, no commercial-readiness claim, no public-launch claim, no compliance-certification claim, no external publication, and no deployment claim.
-->

# Foundation Claim Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** claim-boundary preparation means separating what the
> repository proves from what the public site says, what a runtime proves, what
> legal/business review would prove, and what future customers or pilots would
> need. It does not promote any of those claims.

Witness packet: [`../examples/foundation_claim_boundary_witness.awaiting_evidence.json`](../examples/foundation_claim_boundary_witness.awaiting_evidence.json)

Rule: Claim-boundary preparation is a local planning boundary, not a claim-promotion certificate.

No production-health claim, endpoint-readiness claim, customer-readiness claim,
pilot-readiness claim, legal-clearance claim, commercial-readiness claim,
public-launch claim, compliance-certification claim, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode can produce real local evidence: validators, tests, receipts,
docs, and source-control packets. Those facts are useful, but they do not prove
public production health, customer readiness, legal clearance, commercial
readiness, or deployment readiness.

This boundary keeps claim categories separate:

1. Repository proof can show local files and checks.
2. Public copy can describe direction without inviting access.
3. Runtime proof needs deployed endpoint evidence before public health claims.
4. Legal/business claims need qualified review or signed witness evidence.
5. Customer or pilot claims need support, privacy, intake, and rollback gates.
6. Claim promotion needs explicit evidence and a later signed witness.

## Current State

```text
claim_boundary_state=AwaitingEvidence
production_health_claimed=false
endpoint_readiness_claimed=false
customer_readiness_claimed=false
pilot_readiness_claimed=false
legal_clearance_claimed=false
commercial_readiness_claimed=false
public_launch_claimed=false
compliance_certification_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Claim Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Repository proof claims | Record local validators, tests, receipts, and docs. | Do not treat local evidence as production health. |
| Public-copy claims | Keep wording Foundation Mode compatible. | Do not invite access, waitlists, pilots, customers, or paid use. |
| Runtime-proof claims | List what runtime evidence would be needed later. | Do not claim endpoints, uptime, public health, or deployment readiness. |
| Legal/business claims | List review questions and required future evidence. | Do not claim legal clearance, company readiness, patent protection, or commercial readiness. |
| Customer/pilot claims | List future support, intake, privacy, and rollback gates. | Do not claim pilot readiness or customer readiness. |
| Deployment claims | List deployment witness prerequisites. | Do not deploy or claim deployment readiness. |
| Evidence-promotion questions | Draft the future promotion checklist. | Do not promote claims without a signed witness. |
| Claim-review handoff | Draft reviewer questions. | Do not imply approval by future reviewers. |

## Operator Procedure

1. State the evidence class before making any claim.
2. Keep repository-local evidence, public-copy claims, runtime claims,
   legal/business claims, and customer/pilot claims separate.
3. Do not convert local validators or passing tests into public health,
   endpoint, legal, commercial, customer, pilot, or deployment claims.
4. Keep private account details, endpoint targets, reviewer identities, and
   provider internals out of public witness packets.
5. Treat every claim surface as `AwaitingEvidence` until a later signed witness
   promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_claim_boundary.py
```

The validator checks that the claim-boundary witness:

1. keeps every claim surface in `AwaitingEvidence`;
2. keeps production health, endpoint readiness, customer readiness, pilot
   readiness, legal clearance, commercial readiness, public launch, compliance
   certification, external publication, and deployment blocked;
3. rejects URL, email, private path, endpoint, customer, legal, business,
   compliance, launch, deployment, account, provider, or secret-shaped values;
   and
4. rejects claim-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| See current public claim truth | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |
| Check naming/public-copy posture | [Public Naming Readiness](PUBLIC_NAMING_READINESS.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: production health not claimed, endpoint readiness not claimed, customer readiness not claimed, pilot readiness not claimed, legal clearance not claimed, commercial readiness not claimed, public launch not claimed, compliance certification not claimed, external publication blocked, deployment blocked
  Open issues: repository-proof promotion evidence, public-copy promotion evidence, runtime-proof evidence, legal/business evidence, customer/pilot evidence, deployment-witness evidence, evidence-promotion checklist, and claim-review handoff remain AwaitingEvidence
  Next action: run the claim-boundary validator before any future claim-promotion request
