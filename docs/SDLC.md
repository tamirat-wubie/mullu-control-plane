# Mullu SDLC / SDLD

Purpose: define the governed software delivery lifecycle doctrine for Mullu software changes.
Governance scope: OCE lifecycle field completeness, RAG artifact linkage, CDCV stage transition causality, CQTE decidable gates, UWMA receipt anchoring, and PRS closure evidence.
Dependencies: `docs/SDLC_GOVERNANCE_POLICY.md`, `docs/SDLC_STATE_MACHINE.md`, `docs/SDLC_RELEASE_POLICY.md`, `docs/SDLC_SECURITY_REVIEW.md`, `docs/SDLC_PR_ENFORCEMENT.md`, `docs/main-protection-ruleset-witness.json`, `schemas/sdlc_*.schema.json`, `examples/sdlc/*.json`, `examples/sdlc_route/*.json`, `scripts/route_sdlc.py`, and `scripts/validate_sdlc_*.py`.
Invariants: no software change, release, deployment, or production claim advances without evidence, validation, receipt, and closure.

## Architecture

SDLD is the doctrine name. The machine-readable artifact prefix is `sdlc` because the contract governs the Software Development Life Cycle.

```text
SDLC = UAO for software changes
```

The governed path is:

```text
idea
-> intake
-> requirement
-> design
-> work plan
-> implementation
-> verification
-> security review
-> release readiness
-> deployment readiness
-> operation witness
-> feedback
-> closure
```

The repository implementation is intentionally non-runtime in this phase:

```text
doctrine docs -> schema contracts -> example fixtures -> validators -> workspace preflight required gates
```

The repo-owned route helper is:

```text
request text -> scripts/route_sdlc.py -> SDLC route used -> required skill lanes -> PR evidence
```

`python scripts/route_sdlc.py "CI failed on the SDLC Governance Gate for a PR"` emits the deterministic SDLC route used for a change. `python scripts/validate_sdlc_route.py` validates checked route fixtures and the PR evidence hooks.

The read-only dashboard projection is:

```text
change -> stage -> blockers -> evidence -> receipt -> closure
```

`/software/receipts/sdlc/dashboard` exposes this projection for operator review without mutating lifecycle state.

`/software/receipts/dashboard` exposes live software receipt store counts, terminal/open request totals, stage distribution, and bounded operator-review signals without replaying or mutating receipt chains.

## Algorithm

1. Intake captures owner, source, scope, risk, target surfaces, and evidence.
2. Requirement defines measurable success criteria, non-goals, constraints, acceptance tests, and evidence needed.
3. Design binds affected modules, schema impact, security model, rollback plan, migration plan, and test plan.
4. Work plan orders implementation steps, dependencies, validators, tests, expected artifacts, and owner.
5. Transition receipt records each governed movement between lifecycle states with evidence, receipt refs, blockers, UAO ref, and causal trace.
6. Implementation receipt records constructive deltas, fracture deltas, changed files, test changes, documentation changes, schema changes, validator changes, and rollback refs.
7. Verification records commands, validator outputs, warnings, failed checks, and receipt references.
8. Security review classifies impact categories, threat model, findings, mitigations, residual risk, and receipts.
9. Release readiness binds version, change set, evidence-bound claims, migrations, known limitations, and rollback plan.
10. Deployment readiness binds environment, runtime host, health check, runtime conformance, witness status, and rollback command.
11. Recovery handoff records rollback state, rollback refs, incident recovery refs, accepted risk refs, effect boundaries, and terminal closure linkage.
12. Closure records terminal state, outcome, receipts, remaining blockers, learning notes, and next action.

## Artifact Set

The canonical lifecycle example under `examples/sdlc/` represents the UAO validator change from intake through closure. Each artifact validates against a strict schema and is cross-checked by `scripts/validate_sdlc_artifact.py`.

Canonical inventory closure is named `sdlc_inventory_closure`. Design `schema_changes`, work-plan `expected_artifacts`, implementation `changed_files` and `schema_changes`, and verification `coverage_refs` must include every schema and example in the canonical SDLC artifact inventory, so added lifecycle artifacts cannot drift outside the proof chain.

Workspace preflight closure is named `sdlc_workspace_preflight_closure`. Verification commands, validator outputs, verification `coverage_refs`, and terminal closure `receipts` must retain the workspace governance preflight receipt, so a closure cannot cite preflight doctrine without carrying the preflight witness.

Branch protection witness closure is named `sdlc_branch_ruleset_witness`. Implementation `documentation_changes` and verification `coverage_refs` must retain `docs/main-protection-ruleset-witness.json`, so PR enforcement cannot claim default-branch protection without carrying the retained ruleset witness.

| Artifact | Schema | Gate |
| --- | --- | --- |
| Change request | `schemas/sdlc_change_request.schema.json` | no intake without owner, source, scope, and target surface |
| Requirement | `schemas/sdlc_requirement.schema.json` | no design without success criteria |
| Design decision | `schemas/sdlc_design_decision.schema.json` | no implementation without rollback path and test plan |
| Work plan | `schemas/sdlc_work_plan.schema.json` | no coding without ordered work plan for medium and high risk |
| Implementation receipt | `schemas/sdlc_implementation_receipt.schema.json` | no verification without implementation deltas, changed files, tests, docs, and rollback refs |
| Transition receipt | `schemas/sdlc_transition_receipt.schema.json` | no state movement without transition evidence, receipt refs, and blocker classification |
| Verification receipt | `schemas/sdlc_verification_receipt.schema.json` | no readiness claim without validation receipt |
| Security review | `schemas/sdlc_security_review.schema.json` | no release with unresolved critical or high findings |
| Release candidate | `schemas/sdlc_release_candidate.schema.json` | no release note may claim more than evidence supports |
| Deployment candidate | `schemas/sdlc_deployment_candidate.schema.json` | no production claim without deployment witness and public health evidence |
| Recovery handoff receipt | `schemas/sdlc_recovery_handoff_receipt.schema.json` | no terminal closure without rollback state, incident path, accepted-risk refs, and effect boundaries |
| Closure receipt | `schemas/sdlc_closure_receipt.schema.json` | no closure without receipt and learning |

## UAO Binding

Effect-bearing SDLC action -> UAO required.

Effect-bearing SDLC actions include schema changes, validator changes, policy changes, PR merge, release publication, deployment, capability maturity changes, blocker closure, and witness publication.

Each SDLC gate decision must carry:

```text
uao_ref
causal_decision_trace_ref
receipt_ref
```

This required triplet is the `sdlc_gate_decision_envelope`. Every non-terminal SDLC artifact carries exactly this envelope. Terminal closure carries retained arrays of every upstream `uao_ref`, `causal_decision_trace_ref`, and `receipt_ref`, so no stage can be closed with a dropped admission trace.

Implementation deltas are first-class evidence:

```text
sdlc_implementation_receipt := <change_id, plan_id, constructive_deltas, fracture_deltas, changed_files, test_changes, documentation_changes, schema_changes, validator_changes, rollback_refs, uao_ref, causal_decision_trace_ref, receipt_ref>
```

Every state change also emits a transition receipt:

```text
sdlc_transition_receipt := <from_state, to_state, decision, required_evidence_refs, required_receipt_refs, blockers, uao_ref, causal_decision_trace_ref, receipt_ref>
```

Recovery handoff is first-class terminal evidence:

```text
sdlc_recovery_handoff_receipt := <change_id, rollback_state, rollback_refs, incident_handoff_required, incident_recovery_refs, accepted_risk_refs, effect_boundary_refs, terminal_closure_ref, uao_ref, causal_decision_trace_ref, receipt_ref>
```

No raw private reasoning field may appear in an SDLC artifact.

## Verification

Run:

```powershell
python scripts/validate_sdlc_artifact.py
python scripts/validate_sdlc_route.py
python scripts/validate_sdlc_state_machine.py
python scripts/validate_sdlc_release_readiness.py --strict
python scripts/validate_sdlc_security_review.py --strict
python scripts/validate_sdlc_pr_enforcement.py
python scripts/route_sdlc.py "CI failed on the SDLC Governance Gate for a PR"
python scripts/run_workspace_governance_checks.py --json --max-workers 8 --per-check-timeout-seconds 120 --receipt-path .tmp/workspace-governance-preflight-receipt.json
python -m pytest mcoi/tests/test_sdlc_dashboard.py -q
python -m pytest tests/test_validate_sdlc_artifact.py tests/test_validate_sdlc_route.py tests/test_validate_sdlc_state_machine.py tests/test_validate_sdlc_release_readiness.py tests/test_sdlc_security_review.py tests/test_validate_sdlc_pr_enforcement.py -q
python scripts/run_workspace_governance_checks.py --max-workers 8 --per-check-timeout-seconds 120
```

## Doctrine

```text
No idea without intake.
No intake without requirement.
No requirement without design.
No design without rollback.
No implementation without delta receipt.
No implementation without tests.
No test without receipt.
No release without evidence.
No deployment without witness.
No claim without proof.
No inventory drift between lifecycle schemas, examples, implementation receipts, and verification coverage.
No SDLC route used claim without `scripts/route_sdlc.py` or `scripts/validate_sdlc_route.py` evidence.
No terminal closure without workspace preflight receipt retention.
No PR enforcement claim without branch protection witness retention.
No closure without recovery handoff.
No closure without learning.
```
