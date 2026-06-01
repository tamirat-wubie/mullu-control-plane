## Summary

<!-- Describe the constructive delta and the invariant this PR protects. -->

## Governance posture

- [ ] No silent authority expansion.
- [ ] New write or mutation paths are explicit and gated.
- [ ] Runtime-only contracts are not presented as public protocol surface.

## SDLC / SDLD evidence

Every governed software delivery PR must either attach the lifecycle artifacts or explain why the change is documentation-only or read-only.

- [ ] Change request is linked or included.
- [ ] Requirement is linked or included.
- [ ] Design decision includes rollback path and test plan.
- [ ] Work plan orders implementation and verification steps.
- [ ] Implementation receipt records constructive deltas, fracture deltas, changed files, test changes, documentation changes, schema changes, validator changes, and rollback refs.
- [ ] Transition receipt records state movement, evidence, receipt refs, and blockers.
- [ ] Verification receipt records commands, warnings, and failures.
- [ ] Security review records impact categories, required checks, findings, and residual risk.
- [ ] Release or deployment candidate does not claim more than evidence supports.
- [ ] Recovery handoff receipt records rollback state, rollback refs, incident recovery refs, accepted-risk refs, effect boundaries, and terminal closure linkage.
- [ ] Gate decision envelope is present on each non-terminal artifact: `uao_ref`, `causal_decision_trace_ref`, and `receipt_ref`.
- [ ] Inventory closure proves design, work plan, implementation receipt, and verification receipt retain canonical schema and example coverage.
- [ ] Workspace preflight receipt is retained through verification output, verification coverage, and terminal closure.
- [ ] Branch protection witness confirms `main-protection` required status contexts.
- [ ] Closure receipt records outcome, receipts, remaining blockers, learning, and next action.
- [ ] Closure receipt retains every upstream UAO, causal trace, implementation receipt, transition receipt, recovery handoff receipt, and receipt reference.
- [ ] Rollback or incident handoff path is stated for effect-bearing changes.

## Schema surface boundary

If this PR adds or changes `schemas/*.schema.json`:

- [ ] The schema is intended as public Mullu Governance Protocol surface.
- [ ] The schema `$id` is stable and uses `urn:mullusi:schema:<schema-id>:<version>`.
- [ ] `schemas/mullu_governance_protocol.manifest.json` has exactly one matching entry.
- [ ] `python scripts/validate_protocol_manifest.py` passes.
- [ ] The PR body states backward-compatibility and version impact.

If this PR adds runtime-only contracts:

- [ ] No new public `schemas/*.schema.json` file was added accidentally.
- [ ] Runtime contract tests cover validation and rejection behavior.
- [ ] Docs identify the boundary when the shape could be mistaken for public API.

## Validation

```bash
python scripts/validate_protocol_manifest.py
python scripts/validate_release_status.py --strict
python scripts/validate_sdlc_artifact.py
python scripts/validate_sdlc_state_machine.py
python scripts/validate_sdlc_release_readiness.py --strict
python scripts/validate_sdlc_security_review.py --strict
python scripts/validate_sdlc_pr_enforcement.py
python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json
```

Additional targeted checks:

```bash
# add targeted tests here
```
