# ProblemStar Compilation Receipt

Purpose: define the public read-only receipt proving that raw platform input was compiled into a Phi-GPS v3 `ProblemStar` before solver routing.
Governance scope: OCE field completeness, RAG linkage between compiler surfaces, CDCV causal traceability, CQTE decidable guard checks, UWMA receipt anchoring, SRCA bounded routing, and PRS validation closure.
Dependencies: `docs/PHI_CANONICAL_SPEC.md`, `schemas/problem_star_compilation_receipt.schema.json`, `examples/problem_star_compilation_receipt.foundation.json`, and `scripts/validate_problem_star_compilation_receipt.py`.
Invariants: compilation evidence does not grant runtime registration, connector authority, deployment authority, or terminal closure.

## Boundary

The `ProblemStar` compilation receipt is an epistemic proof artifact. It records that the platform separated raw input into evidence, assumptions, unknowns, contradictions, goals, constraints, risks, available actions, and proof obligations before solver routing.

It is not a runtime solver registration, external adapter receipt, deployment witness, or authority grant.

## Contract Files

| Artifact | Role |
| --- | --- |
| `schemas/problem_star_compilation_receipt.schema.json` | Public schema for the receipt. |
| `examples/problem_star_compilation_receipt.foundation.json` | Foundation Mode example receipt. |
| `scripts/validate_problem_star_compilation_receipt.py` | Deterministic validator for schema, example, field order, separation, guards, and receipt refs. |
| `tests/test_validate_problem_star_compilation_receipt.py` | Focused positive, negative, drift, and SDLC evidence tests. |

## Required Separation

The receipt must preserve these surfaces as separate fields:

1. Evidence.
2. Assumptions.
3. Unknowns.
4. Contradictions.
5. Goals.
6. Constraints.
7. Risks.
8. Available actions.
9. Proof obligations.

Merging evidence with assumptions, dropping proof obligations, or hiding contradictions invalidates the receipt.

## ProblemStar Order

The kernel draft must preserve the canonical Phi-GPS v2.2 field order:

```text
W, B, O, I, G, U, Lambda, N, A_e, A_w, T, R, K, Pi
```

## Authority Denials

The receipt must explicitly keep these guards false:

| Guard | Required value |
| --- | --- |
| `runtime_registration_claimed` | `false` |
| `execution_authority_granted` | `false` |
| `connector_authority_granted` | `false` |
| `deployment_claimed` | `false` |
| `terminal_closure` | `false` |

## Repository World-State Evidence

Repository observation may enter `separated_surfaces.evidence` only through the
World State Plane binding:

```text
bind_repository_world_state_projection_to_problem_star_evidence(projection, planning_claims)
```

The binding admits only same-tenant, same-packet, planning-only claims returned
by `WorldStateStore.planning_claims`. Foundation packets, `ProofState Unknown`
packets, failed command observations, and projections with open contradictions
produce no evidence items and emit proof obligations before solver routing.

## Validation

```powershell
python scripts/validate_problem_star_compilation_receipt.py
python -m pytest tests/test_validate_problem_star_compilation_receipt.py -q
```

STATUS:
  Completeness: 100%
  Invariants verified: ProblemStar field order, separation before solver routing, authority denial, repository world-state evidence binding, Mfidel atomicity preservation
  Open issues: external adapter evidence remains AwaitingEvidence
  Next action: keep the receipt as governed-loop evidence without runtime authority
