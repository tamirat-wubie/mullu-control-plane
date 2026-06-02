<!--
Purpose: define the Foundation Mode gap-register boundary for local public-safe gap question drafting without claiming gap-register completeness, gap closure, priority closure, owner assignment, remediation readiness, roadmap commitment, evidence promotion, terminal closure, test pass, implementation, publication, or deployment.
Governance scope: architecture gap questions, module gap questions, interface gap questions, dependency gap questions, invariant gap questions, hazard gap questions, proof-reference gap questions, runtime gap questions, rollback gap questions, operator gap questions, public-safe planning, and readiness blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md, examples/foundation_gap_register_witness.awaiting_evidence.json, scripts/validate_foundation_gap_register_boundary.py.
Invariants: no gap-register completeness claim, no gap closure claim, no priority closure claim, no owner assignment, no remediation readiness claim, no roadmap commitment, no evidence promotion, no terminal closure claim, no test pass claim, no refactor approval, no implementation approval, no external publication, and no deployment claim.
-->

# Foundation Gap Register Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** gap-register preparation means drafting local public-safe
> questions about what is still missing, unknown, inconsistent, unverified, or
> too weak to trust. It does not close those gaps, assign owners, set a roadmap,
> approve remediation, prove tests, publish, or deploy anything.

Witness packet: [`../examples/foundation_gap_register_witness.awaiting_evidence.json`](../examples/foundation_gap_register_witness.awaiting_evidence.json)

Rule: Gap-register preparation is a local planning boundary, not a
gap-register-completion, gap-closure, priority-closure, owner-assignment,
remediation-readiness, roadmap-commitment, evidence-promotion,
terminal-closure, test-pass, refactor-approval, implementation-approval,
publication, or deployment certificate.

No gap-register completeness, gap closure, priority closure, owner assignment,
remediation readiness, roadmap commitment, evidence promotion, terminal
closure, test pass, refactor approval, implementation approval, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Proof references say what evidence would be needed. Gap registers name what is
still missing before any claim can be trusted. This boundary lets the repository
prepare gap questions without pretending the gaps are resolved or converted
into an executable roadmap.

This is preparation only:

1. The repository can name gap-register surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature gap closure, priority closure, owner
   assignment, remediation readiness, roadmap commitment, evidence promotion,
   terminal closure, tests, implementation, publication, or deployment claims.
4. Private paths, endpoints, provider identifiers, gap targets, owner names,
   remediation ids, roadmap dates, test results, secrets, credentials,
   customer data, and deployment targets stay out of the public packet.

## Current State

```text
gap_register_boundary_state=AwaitingEvidence
gap_register_complete_claimed=false
gap_closure_claimed=false
gap_priority_closed_claimed=false
gap_owner_assigned=false
remediation_ready_claimed=false
roadmap_commitment_allowed=false
evidence_promotion_allowed=false
terminal_closure_claimed=false
test_pass_claimed=false
refactor_approval_allowed=false
implementation_approval_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Gap-Register Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Architecture gaps | Draft questions about missing architecture evidence or unclear boundaries. | Do not claim architecture gap closure. |
| Module gaps | Draft questions about missing module identity, ownership, or contract evidence. | Do not assign module owners. |
| Interface gaps | Draft questions about unclear input, output, error, and handoff evidence. | Do not claim interface readiness. |
| Dependency gaps | Draft questions about missing package, service, provider, or version evidence. | Do not approve installs or provider binding. |
| Invariant gaps | Draft questions about unproven, unenforced, or conflicting invariants. | Do not claim invariant closure. |
| Hazard gaps | Draft questions about unclassified, unmitigated, or unreviewed hazards. | Do not claim mitigation readiness. |
| Proof-reference gaps | Draft questions about missing evidence links or weak proof references. | Do not claim proof coverage closure. |
| Runtime gaps | Draft questions about missing runtime, endpoint, database, or migration evidence. | Do not claim runtime readiness. |
| Rollback gaps | Draft questions about missing recovery, rollback, replay, or restore evidence. | Do not claim rollback readiness. |
| Operator gaps | Draft questions about solo-operator capacity, support, review, and escalation gaps. | Do not claim owner approval or support readiness. |

## Operator Procedure

1. Pick one gap-register surface from the table.
2. Draft only public-safe gap questions.
3. Avoid URLs, emails, private paths, endpoint targets, provider targets, gap
   ids, owner names, remediation ids, roadmap dates, evidence targets,
   terminal-closure records, test results, secrets, credentials, customer
   identifiers, implementation ids, refactor ids, or deployment targets.
4. Mark unknown gaps, priorities, ownership, remediation paths, roadmap
   effects, evidence, terminal closure, tests, implementation, and exposure
   points as `AwaitingEvidence`.
5. Do not use this register to authorize remediation, refactor,
   implementation, roadmap commitments, publication, external exposure,
   customer access, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_gap_register_boundary.py
```

The validator checks that the gap-register witness:

1. keeps gap-register completeness, gap closure, priority closure, owner
   assignment, remediation readiness, roadmap commitment, evidence promotion,
   terminal closure, test pass, refactor approval, implementation approval,
   publication, and deployment disabled;
2. keeps every gap-register surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, gap, owner,
   remediation, roadmap, proof, evidence, terminal, test, customer, secret,
   credential, implementation, refactor, publication, or deployment shaped
   values; and
4. rejects gap-closure promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare proof references safely | [Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md) |
| Prepare local workstation safely | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: gap-register completeness blocked, gap closure blocked, priority closure blocked, owner assignment blocked, remediation readiness blocked, roadmap commitment blocked, evidence promotion blocked, terminal closure blocked, test pass blocked, refactor approval blocked, implementation approval blocked, external publication blocked, deployment blocked
  Open issues: architecture-gap evidence, module-gap evidence, interface-gap evidence, dependency-gap evidence, invariant-gap evidence, hazard-gap evidence, proof-reference-gap evidence, runtime-gap evidence, rollback-gap evidence, and operator-gap evidence remain AwaitingEvidence
  Next action: run the gap-register validator before using gap notes as readiness evidence
