<!--
Purpose: define the Foundation Mode invariant-map boundary for local public-safe invariant question drafting without claiming invariant-map completeness, proof readiness, enforcement readiness, conflict resolution, monitor readiness, runtime readiness, owner approval, test pass, implementation, publication, or deployment.
Governance scope: identity invariant questions, state invariant questions, boundary invariant questions, interface invariant questions, dependency invariant questions, governance invariant questions, evidence invariant questions, rollback invariant questions, operator invariant questions, public-safe planning, and readiness blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md, examples/foundation_invariant_map_witness.awaiting_evidence.json, scripts/validate_foundation_invariant_map_boundary.py.
Invariants: no invariant-map completeness claim, no invariant proof readiness claim, no invariant enforcement readiness claim, no invariant conflict resolution claim, no invariant monitor readiness claim, no runtime invariant readiness claim, no owner approval assignment, no test pass claim, no refactor approval, no implementation approval, no external publication, and no deployment claim.
-->

# Foundation Invariant Map Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** invariant-map preparation means drafting local public-safe
> questions about what must stay true across identity, state, boundaries,
> interfaces, dependencies, governance, evidence, rollback, and operator work.
> It does not prove invariants are complete, enforced, tested, monitored,
> ready at runtime, implemented, publishable, or deployable.

Witness packet: [`../examples/foundation_invariant_map_witness.awaiting_evidence.json`](../examples/foundation_invariant_map_witness.awaiting_evidence.json)

Rule: Invariant-map preparation is a local planning boundary, not an
invariant-map-completion, invariant-proof-readiness, enforcement-readiness,
conflict-resolution, monitor-readiness, runtime-readiness, owner-approval,
test-pass, refactor-approval, implementation-approval, publication, or
deployment certificate.

No invariant-map completeness, invariant proof readiness, invariant
enforcement readiness, invariant conflict resolution, invariant monitor
readiness, runtime invariant readiness, owner approval assignment, test pass,
refactor approval, implementation approval, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Dependencies show what surfaces rely on. Invariants show what must not be
broken while those surfaces evolve. This boundary lets the repository prepare
invariant questions without claiming proofs, enforcement, monitors, runtime
checks, tests, or implementation approval.

This is preparation only:

1. The repository can name invariant-map surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature invariant proof, enforcement, monitoring,
   runtime, owner, test, implementation, publication, or deployment claims.
4. Private paths, endpoint targets, provider identifiers, test results,
   monitor targets, secrets, credentials, customer data, and deployment targets
   stay out of the public packet.

## Current State

```text
invariant_map_boundary_state=AwaitingEvidence
invariant_map_complete_claimed=false
invariant_proof_ready_claimed=false
invariant_enforcement_ready_claimed=false
invariant_conflict_resolved_claimed=false
invariant_monitor_ready_claimed=false
runtime_invariant_ready_claimed=false
owner_approval_assigned=false
test_pass_claimed=false
refactor_approval_allowed=false
implementation_approval_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Invariant-Map Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Identity invariants | Draft identity-preservation questions. | Do not claim identity invariants are proven. |
| State invariants | Draft state-transition and write-safety questions. | Do not claim state invariants are enforced. |
| Boundary invariants | Draft repository, product, runtime, and trust-boundary questions. | Do not claim boundary closure. |
| Interface invariants | Draft input, output, and error-path invariant questions. | Do not claim interface invariant readiness. |
| Dependency invariants | Draft package, service, provider, and data dependency invariant questions. | Do not claim dependency invariant readiness. |
| Governance invariants | Draft policy, approval, receipt, and rejection invariant questions. | Do not claim governance enforcement readiness. |
| Evidence invariants | Draft witness, receipt, and trace invariant questions. | Do not claim evidence closure. |
| Rollback invariants | Draft rollback, recovery, replay, and reversibility questions. | Do not claim rollback readiness. |
| Operator invariants | Draft solo-operator workflow and support invariant questions. | Do not claim owner, support, or deployment readiness. |

## Operator Procedure

1. Pick one invariant surface from the table.
2. Draft only public-safe invariant questions.
3. Avoid URLs, emails, private paths, endpoint targets, account identifiers,
   provider targets, monitor targets, proof ids, test results, secrets,
   credentials, customer identifiers, implementation ids, refactor ids, or
   deployment targets.
4. Mark unknown proofs, enforcement paths, conflicts, monitors, runtime
   behavior, owner approval, tests, implementation, and exposure points as
   `AwaitingEvidence`.
5. Do not use this map to authorize enforcement, refactor, implementation,
   publication, external exposure, customer access, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_invariant_map_boundary.py
```

The validator checks that the invariant-map witness:

1. keeps invariant-map completeness, proof readiness, enforcement readiness,
   conflict resolution, monitor readiness, runtime readiness, owner approval,
   test pass, refactor approval, implementation approval, publication, and
   deployment disabled;
2. keeps every invariant-map surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, invariant,
   proof, monitor, test, customer, secret, credential, implementation,
   refactor, publication, or deployment shaped values; and
4. rejects invariant-readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare dependency graphs safely | [Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md) |
| Prepare local workstation safely | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: invariant-map completeness blocked, invariant proof readiness blocked, invariant enforcement readiness blocked, invariant conflict resolution blocked, invariant monitor readiness blocked, runtime invariant readiness blocked, owner approval blocked, test pass blocked, refactor approval blocked, implementation approval blocked, external publication blocked, deployment blocked
  Open issues: identity-invariant evidence, state-invariant evidence, boundary-invariant evidence, interface-invariant evidence, dependency-invariant evidence, governance-invariant evidence, evidence-invariant evidence, rollback-invariant evidence, and operator-invariant evidence remain AwaitingEvidence
  Next action: run the invariant-map validator before using invariant notes as readiness evidence
