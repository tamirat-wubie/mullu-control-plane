<!--
Purpose: define the Foundation Mode proof-reference boundary for local public-safe proof question drafting without claiming proof-reference completeness, proof coverage closure, evidence promotion, terminal closure, verification pass, proof approval, runtime proof readiness, owner approval, test pass, implementation, publication, or deployment.
Governance scope: architecture proof-reference questions, module proof-reference questions, interface proof-reference questions, dependency proof-reference questions, invariant proof-reference questions, hazard proof-reference questions, runtime proof-reference questions, rollback proof-reference questions, operator proof-reference questions, public-safe planning, and readiness blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md, examples/foundation_proof_reference_witness.awaiting_evidence.json, scripts/validate_foundation_proof_reference_boundary.py.
Invariants: no proof-reference completeness claim, no proof coverage closure claim, no evidence promotion, no terminal closure claim, no verification pass claim, no proof approval assignment, no runtime proof readiness claim, no owner approval assignment, no test pass claim, no refactor approval, no implementation approval, no external publication, and no deployment claim.
-->

# Foundation Proof Reference Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** proof-reference preparation means drafting local public-safe
> questions that say what kind of evidence would later be needed for each
> architecture, module, interface, dependency, invariant, hazard, runtime,
> rollback, and operator claim. It does not prove coverage, approve evidence,
> close verification, authorize implementation, publish, or deploy anything.

Witness packet: [`../examples/foundation_proof_reference_witness.awaiting_evidence.json`](../examples/foundation_proof_reference_witness.awaiting_evidence.json)

Rule: Proof-reference preparation is a local planning boundary, not a
proof-reference-completion, proof-coverage-closure, evidence-promotion,
terminal-closure, verification-pass, proof-approval, runtime-proof-readiness,
owner-approval, test-pass, refactor-approval, implementation-approval,
publication, or deployment certificate.

No proof-reference completeness, proof coverage closure, evidence promotion,
terminal closure, verification pass, proof approval assignment, runtime proof
readiness, owner approval assignment, test pass, refactor approval,
implementation approval, external publication, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

Hazard maps name what could break. Proof references name what a later review
would need before a claim could be trusted. This boundary lets the repository
prepare proof questions without pretending the proof exists, has been reviewed,
has passed tests, or can close a readiness decision.

This is preparation only:

1. The repository can name proof-reference surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature proof coverage, evidence promotion,
   verification pass, terminal closure, proof approval, runtime readiness,
   owner approval, tests, implementation, publication, or deployment claims.
4. Private paths, endpoints, provider identifiers, receipt targets, evidence
   targets, verification results, secrets, credentials, customer data, and
   deployment targets stay out of the public packet.

## Current State

```text
proof_reference_boundary_state=AwaitingEvidence
proof_reference_complete_claimed=false
proof_coverage_closed_claimed=false
evidence_promotion_allowed=false
terminal_closure_claimed=false
verification_pass_claimed=false
proof_approval_assigned=false
runtime_proof_ready_claimed=false
owner_approval_assigned=false
test_pass_claimed=false
refactor_approval_allowed=false
implementation_approval_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Proof-Reference Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Architecture proof references | Draft questions for what evidence would support architecture boundaries. | Do not claim architecture proof coverage. |
| Module proof references | Draft questions for what evidence would support module identity and ownership. | Do not claim module proof approval. |
| Interface proof references | Draft questions for what evidence would support inputs, outputs, and error paths. | Do not claim interface verification pass. |
| Dependency proof references | Draft questions for what evidence would support packages, services, and providers. | Do not claim dependency proof closure. |
| Invariant proof references | Draft questions for what evidence would support invariant proof and enforcement. | Do not claim invariant proof readiness. |
| Hazard proof references | Draft questions for what evidence would support hazard classification and mitigation. | Do not claim hazard proof closure. |
| Runtime proof references | Draft questions for what evidence would support runtime behavior. | Do not claim runtime proof readiness. |
| Rollback proof references | Draft questions for what evidence would support rollback and replay. | Do not claim rollback proof readiness. |
| Operator proof references | Draft questions for what evidence would support solo-operator readiness. | Do not claim owner approval or test pass. |

## Operator Procedure

1. Pick one proof-reference surface from the table.
2. Draft only public-safe proof questions.
3. Avoid URLs, emails, private paths, endpoint targets, provider targets,
   proof identifiers, evidence targets, receipt targets, verification results,
   terminal-closure records, test results, secrets, credentials, customer
   identifiers, implementation ids, refactor ids, or deployment targets.
4. Mark unknown proof references, coverage, evidence, verification, terminal
   closure, approvals, runtime behavior, owner approval, tests,
   implementation, and exposure points as `AwaitingEvidence`.
5. Do not use this boundary to authorize proof coverage, evidence promotion,
   implementation, refactor, publication, external exposure, customer access,
   or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_proof_reference_boundary.py
```

The validator checks that the proof-reference witness:

1. keeps proof-reference completeness, proof coverage closure, evidence
   promotion, terminal closure, verification pass, proof approval, runtime
   proof readiness, owner approval, test pass, refactor approval,
   implementation approval, publication, and deployment disabled;
2. keeps every proof-reference surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, proof,
   evidence, receipt, verification, terminal, test, customer, secret,
   credential, implementation, refactor, publication, or deployment shaped
   values; and
4. rejects proof-readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare hazard maps safely | [Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md) |
| Prepare local workstation safely | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: proof-reference completeness blocked, proof coverage closure blocked, evidence promotion blocked, terminal closure blocked, verification pass blocked, proof approval blocked, runtime proof readiness blocked, owner approval blocked, test pass blocked, refactor approval blocked, implementation approval blocked, external publication blocked, deployment blocked
  Open issues: architecture-proof evidence, module-proof evidence, interface-proof evidence, dependency-proof evidence, invariant-proof evidence, hazard-proof evidence, runtime-proof evidence, rollback-proof evidence, and operator-proof evidence remain AwaitingEvidence
  Next action: run the proof-reference validator before using proof notes as readiness evidence
