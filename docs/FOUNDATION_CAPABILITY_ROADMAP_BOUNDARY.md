<!--
Purpose: define the Foundation Mode capability-roadmap boundary before any capability availability, roadmap commitment, delivery-date, customer, pilot, support, pricing, publication, money-movement, or deployment claim.
Governance scope: capability-family questions, readiness questions, sequencing questions, dependency questions, evidence-gate questions, user-value questions, support-load questions, pricing-exposure questions, public-claim questions, evolution-review questions, publication blocking, money-movement blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md, docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md, examples/foundation_capability_roadmap_witness.awaiting_evidence.json, scripts/validate_foundation_capability_roadmap_boundary.py.
Invariants: no capability inventory completeness claim, no capability availability claim, no roadmap commitment, no delivery-date promise, no final sequencing claim, no dependency activation, no public roadmap, no customer commitment, no pilot commitment, no support commitment, no pricing commitment, no money movement, no external publication, and no deployment claim.
-->

# Foundation Capability Roadmap Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** capability-roadmap preparation means drafting local questions
> about which capability families might come first and what evidence each would
> need. It does not mean any capability is available, scheduled, promised,
> priced, customer-facing, pilot-facing, published, or deployable.

Witness packet: [`../examples/foundation_capability_roadmap_witness.awaiting_evidence.json`](../examples/foundation_capability_roadmap_witness.awaiting_evidence.json)

Rule: Capability-roadmap preparation is a local planning boundary, not a capability-availability, roadmap-commitment, delivery-date, customer, pilot, support, pricing, publication, money-movement, or deployment certificate.

No capability inventory completeness, capability availability, roadmap
commitment, delivery-date promise, final sequencing, dependency activation,
public roadmap, customer commitment, pilot commitment, support commitment,
pricing commitment, money movement, external publication, or deployment claim
is permitted by this boundary.

## What This Boundary Solves

Foundation Mode needs capability planning without creating implied promises.
This includes management, mathematics, algorithm, coding, operations, security,
memory, workflow, computer-use, and swarm capability questions, but the machine
contract stays at the roadmap-commitment boundary.

This boundary separates local roadmap thinking from external commitment:

1. Capability families can be named as local questions.
2. Readiness and evidence gates can be drafted without claiming availability.
3. Sequencing can be sketched without promising order or dates.
4. Dependencies can be mapped without activation.
5. Public, customer, pilot, pricing, support, money, and deployment claims stay blocked.

## Current State

```text
capability_roadmap_boundary_state=AwaitingEvidence
capability_inventory_complete_claimed=false
capability_availability_claimed=false
roadmap_commitment_claimed=false
delivery_date_promised=false
sequencing_final_claimed=false
dependency_activation_allowed=false
public_roadmap_allowed=false
customer_commitment_allowed=false
pilot_commitment_allowed=false
support_commitment_allowed=false
pricing_commitment_allowed=false
money_movement_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Preparation Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Capability-family questions | Draft candidate capability families and boundaries. | Do not claim complete inventory. |
| Capability-readiness questions | Draft evidence needed before a capability can be called available. | Do not claim availability. |
| Sequencing questions | Draft local ordering assumptions. | Do not promise order or delivery dates. |
| Dependency questions | Draft internal and external dependency questions. | Do not activate providers, accounts, services, or infrastructure. |
| Evidence-gate questions | Draft promotion evidence needed per capability family. | Do not promote evidence into availability. |
| User-value questions | Draft which user problem each capability might serve. | Do not claim customer validation or demand. |
| Support-load questions | Draft support and operations questions. | Do not claim support readiness or SLA. |
| Pricing-exposure questions | Draft where pricing questions would arise later. | Do not claim pricing readiness or move money. |
| Public-claim questions | Draft wording risks for later review. | Do not publish a roadmap or availability claim. |
| Evolution-review questions | Draft how roadmap assumptions will be revisited. | Do not freeze a roadmap or commit retention. |

## Operator Procedure

1. Write only local questions, assumptions, and evidence gates.
2. Keep every surface in `AwaitingEvidence`.
3. Do not assign delivery dates, customer promises, support promises, prices, or deployment targets.
4. Route any future promotion through a named evidence witness and `Phi_gov` review.
5. Re-run the validator after any roadmap wording change.

## Validation

```powershell
python scripts/validate_foundation_capability_roadmap_boundary.py
```

STATUS:
  Completeness: 100%
  Invariants verified: no capability inventory completeness claim, no capability availability claim, no roadmap commitment, no delivery-date promise, no final sequencing claim, no dependency activation, no public roadmap, no customer commitment, no pilot commitment, no support commitment, no pricing commitment, no money movement, no external publication, no deployment claim
  Open issues: capability-family evidence, readiness evidence, sequencing evidence, dependency evidence, evidence-gate evidence, user-value evidence, support-load evidence, pricing-exposure evidence, public-claim evidence, and evolution-review evidence remain AwaitingEvidence
  Next action: run the capability-roadmap validator before any future capability availability, roadmap, date, customer, pilot, support, pricing, money, publication, or deployment claim
