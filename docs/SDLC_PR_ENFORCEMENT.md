# SDLC PR Enforcement

Purpose: bind governed software delivery evidence to pull request review, CI, branch protection, and merge readiness.
Governance scope: OCE PR evidence completeness, RAG PR-to-artifact linkage, CDCV merge gate causality, CQTE decidable check contexts, UWMA CI receipt anchoring, and PRS review closure.
Dependencies: `.github/pull_request_template.md`, `.github/workflows/ci.yml`, `docs/SDLC.md`, `docs/SDLC_RELEASE_POLICY.md`, `scripts/validate_sdlc_pr_enforcement.py`, and the SDLC validators.
Invariants: a software delivery PR is not ready for merge until SDLC evidence is declared, SDLC validators pass, rollback or incident handoff is stated for effect-bearing changes, and closure evidence is recorded.

## Required PR Evidence

Every effect-bearing software delivery PR must state or link:

1. Change request.
2. Requirement.
3. Design decision with rollback path and test plan.
4. Work plan.
5. Implementation receipt with constructive deltas, fracture deltas, changed files, test changes, documentation changes, schema changes, validator changes, and rollback refs.
6. Transition receipt for lifecycle state movement.
7. Verification receipt.
8. Security review.
9. Release or deployment candidate when release or deployment claims are made.
10. Recovery handoff receipt with rollback state, rollback refs, incident recovery refs, accepted-risk refs, effect boundaries, and terminal closure linkage.
11. Gate decision envelope on each non-terminal artifact: `uao_ref`, `causal_decision_trace_ref`, and `receipt_ref`.
12. Inventory closure proof that design, work plan, implementation receipt, and verification receipt retain the canonical schema and example inventory.
13. Workspace preflight receipt retained through verification output, verification coverage, and terminal closure.
14. Closure receipt with retained upstream UAO, causal trace, implementation receipt, transition receipt, recovery handoff receipt, and receipt references.
15. Rollback or incident handoff path.

Documentation-only and read-only PRs may mark SDLC artifacts not applicable, but the PR must state why no effect-bearing software delivery action is present.

## Required CI Context

The stable required status context is:

```text
SDLC Governance Gate
```

The gate runs:

```powershell
python scripts/validate_sdlc_artifact.py --receipt-path .change_assurance/sdlc_artifact_validation_receipt.json
python scripts/validate_sdlc_state_machine.py
python scripts/validate_sdlc_release_readiness.py --strict
python scripts/validate_sdlc_security_review.py --strict
python scripts/validate_sdlc_pr_enforcement.py
python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json
python -m pytest tests/test_validate_sdlc_artifact.py tests/test_validate_sdlc_state_machine.py tests/test_validate_sdlc_release_readiness.py tests/test_sdlc_security_review.py tests/test_validate_sdlc_pr_enforcement.py -q
```

`Build Verification` depends on `sdlc-governance-gate`, so the existing `main-protection` ruleset cannot pass the aggregate build gate if SDLC validation fails. Branch protection may also require `SDLC Governance Gate` directly.

## Merge Readiness

```text
merge_ready
<=> PR template SDLC evidence complete
and SDLC Governance Gate passed
and workspace governance preflight passed
and gate_decision_envelopes are retained through terminal closure
and sdlc_inventory_closure proves canonical schema and example coverage
and sdlc_workspace_preflight_closure proves workspace preflight command, receipt artifact, validator output, and closure retention
and implementation deltas have `sdlc_implementation_receipt` evidence
and state transitions have `sdlc_transition_receipt` evidence
and recovery handoff has `sdlc_recovery_handoff_receipt` evidence
and release claims are evidence-bound
and rollback_or_incident_handoff exists for effect-bearing changes
and closure receipt records remaining blockers
```

## Failure Handling

If SDLC evidence is missing, the PR remains `AwaitingEvidence`. If SDLC validation fails, the PR is `GovernanceBlocked`. If rollback fails or leaves residual risk, the PR or deployment must link an incident recovery path before terminal closure.
