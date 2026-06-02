<!--
Purpose: define the Foundation Mode architecture-map boundary for local structural mapping without claiming architecture completeness, integration readiness, runtime readiness, implementation approval, publication, or deployment.
Governance scope: system boundary inventory, module inventory, interface map, dependency graph, invariant map, hazard map, proof-reference map, gap register, public-safe planning, and readiness blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md, docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md, examples/foundation_architecture_map_witness.awaiting_evidence.json, scripts/validate_foundation_architecture_map_boundary.py.
Invariants: no architecture-completeness claim, no module-inventory completeness claim, no interface-contract readiness claim, no dependency-graph readiness claim, no invariant-closure claim, no hazard-closure claim, no proof-coverage closure claim, no integration-readiness claim, no runtime-readiness claim, no refactor approval, no implementation approval, no external publication, and no deployment claim.
-->

# Foundation Architecture Map Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** architecture-map preparation means drawing a local map of
> system boundaries, modules, interfaces, dependencies, invariants, hazards,
> proof references, and gaps. It does not prove the architecture is complete,
> ready to integrate, ready to run, approved for refactor, approved for
> implementation, ready to publish, or ready to deploy.

Witness packet: [`../examples/foundation_architecture_map_witness.awaiting_evidence.json`](../examples/foundation_architecture_map_witness.awaiting_evidence.json)

Rule: Architecture-map preparation is a local planning boundary, not an architecture-completion,
integration-readiness, runtime-readiness, implementation, publication, or
deployment certificate.

No architecture-completeness claim, module-inventory completeness claim,
interface-contract readiness claim, dependency-graph readiness claim,
invariant-closure claim, hazard-closure claim, proof-coverage closure claim,
integration-readiness claim, runtime-readiness claim, refactor approval,
implementation approval, external publication, or deployment claim is permitted
by this boundary.

## What This Boundary Solves

Foundation Mode needs structural clarity before broad work. A local
architecture map lets the operator ask "what connects to what?" without
pretending the map is complete or that the system is ready to run publicly.

This is preparation only:

1. The repository can name architecture-map surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature completeness, readiness, approval,
   publication, or deployment claims.
4. Private endpoints, account identifiers, secrets, credentials, customer
   data, and local private paths stay out of the public packet.

## Current State

```text
architecture_map_boundary_state=AwaitingEvidence
architecture_complete_claimed=false
module_inventory_complete_claimed=false
interface_contract_ready_claimed=false
dependency_graph_ready_claimed=false
invariant_closure_claimed=false
hazard_closure_claimed=false
proof_coverage_closure_claimed=false
integration_readiness_claimed=false
runtime_readiness_claimed=false
refactor_approval_allowed=false
implementation_approval_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Architecture-Map Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| System boundary inventory | Name public-safe subsystem boundaries. | Do not claim the architecture is complete. |
| Module inventory | Draft module responsibility questions. | Do not claim module inventory completeness. |
| Interface map | Draft interface and handoff questions. | Do not claim interface-contract readiness. |
| Dependency graph | Draft dependency and adjacency questions. | Do not claim dependency-graph readiness. |
| Invariant map | Name invariants that need evidence. | Do not claim invariant closure. |
| Hazard map | Name hazards and unknowns. | Do not claim hazard closure or safety approval. |
| Proof-reference map | Link public-safe proof references. | Do not claim proof coverage closure. |
| Gap register | Record what remains unknown. | Do not approve implementation, refactor, publication, or deployment. |

## Operator Procedure

1. Choose one subsystem boundary from the docs.
2. Record only public-safe labels, not endpoint values or private paths.
3. Name adjacent modules and dependencies as questions when evidence is weak.
4. Record invariants, hazards, proof references, and gaps separately.
5. Keep every surface in `AwaitingEvidence` until a later signed witness
   promotes one exact item.
6. Do not use the architecture map to authorize refactor, implementation,
   publication, runtime activation, customer access, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_architecture_map_boundary.py
```

The validator checks that the architecture-map witness:

1. keeps architecture completeness, module inventory completeness, interface
   readiness, dependency graph readiness, invariant closure, hazard closure,
   proof coverage closure, integration readiness, runtime readiness, refactor
   approval, implementation approval, external publication, and deployment
   disabled;
2. keeps every architecture-map surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, customer,
   secret, credential, service, implementation, refactor, publication, or
   deployment shaped values; and
4. rejects readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare documentation safely | [Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md) |
| Organize evidence references safely | [Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: architecture-completeness claim blocked, module-inventory completeness claim blocked, interface-contract readiness blocked, dependency-graph readiness blocked, invariant closure blocked, hazard closure blocked, proof-coverage closure blocked, integration readiness blocked, runtime readiness blocked, refactor approval blocked, implementation approval blocked, external publication blocked, deployment blocked
  Open issues: system-boundary evidence, module-inventory evidence, interface-map evidence, dependency-graph evidence, invariant-map evidence, hazard-map evidence, proof-reference evidence, and gap-register evidence remain AwaitingEvidence
  Next action: run the architecture-map boundary validator before using architecture notes as readiness evidence
