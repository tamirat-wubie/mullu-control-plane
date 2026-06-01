# Mullu SDLC / SDLD

Purpose: define the governed software delivery lifecycle doctrine for Mullu software changes.
Governance scope: OCE lifecycle field completeness, RAG artifact linkage, CDCV stage transition causality, CQTE decidable gates, UWMA receipt anchoring, and PRS closure evidence.
Dependencies: `docs/SDLC_GOVERNANCE_POLICY.md`, `docs/SDLC_STATE_MACHINE.md`, `docs/SDLC_RELEASE_POLICY.md`, `docs/SDLC_SECURITY_REVIEW.md`, `docs/SDLC_PR_ENFORCEMENT.md`, `schemas/sdlc_*.schema.json`, `examples/sdlc/*.json`, and `scripts/validate_sdlc_*.py`.
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

## Algorithm

1. Intake captures owner, source, scope, risk, target surfaces, and evidence.
2. Requirement defines measurable success criteria, non-goals, constraints, acceptance tests, and evidence needed.
3. Design binds affected modules, schema impact, security model, rollback plan, migration plan, and test plan.
4. Work plan orders implementation steps, dependencies, validators, tests, expected artifacts, and owner.
5. Transition receipt records each governed movement between lifecycle states with evidence, receipt refs, blockers, UAO ref, and causal trace.
6. Implementation records constructive deltas, fracture deltas, changed files, test changes, and documentation changes.
7. Verification records commands, validator outputs, warnings, failed checks, and receipt references.
8. Security review classifies impact categories, threat model, findings, mitigations, residual risk, and receipts.
9. Release readiness binds version, change set, evidence-bound claims, migrations, known limitations, and rollback plan.
10. Deployment readiness binds environment, runtime host, health check, runtime conformance, witness status, and rollback command.
11. Closure records terminal state, outcome, receipts, remaining blockers, learning notes, and next action.

## Artifact Set

The canonical lifecycle example under `examples/sdlc/` represents the UAO validator change from intake through closure. Each artifact validates against a strict schema and is cross-checked by `scripts/validate_sdlc_artifact.py`.

| Artifact | Schema | Gate |
| --- | --- | --- |
| Change request | `schemas/sdlc_change_request.schema.json` | no intake without owner, source, scope, and target surface |
| Requirement | `schemas/sdlc_requirement.schema.json` | no design without success criteria |
| Design decision | `schemas/sdlc_design_decision.schema.json` | no implementation without rollback path and test plan |
| Work plan | `schemas/sdlc_work_plan.schema.json` | no coding without ordered work plan for medium and high risk |
| Transition receipt | `schemas/sdlc_transition_receipt.schema.json` | no state movement without transition evidence, receipt refs, and blocker classification |
| Verification receipt | `schemas/sdlc_verification_receipt.schema.json` | no readiness claim without validation receipt |
| Security review | `schemas/sdlc_security_review.schema.json` | no release with unresolved critical or high findings |
| Release candidate | `schemas/sdlc_release_candidate.schema.json` | no release note may claim more than evidence supports |
| Deployment candidate | `schemas/sdlc_deployment_candidate.schema.json` | no production claim without deployment witness and public health evidence |
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

Every state change also emits a transition receipt:

```text
sdlc_transition_receipt := <from_state, to_state, decision, required_evidence_refs, required_receipt_refs, blockers, uao_ref, causal_decision_trace_ref, receipt_ref>
```

No raw private reasoning field may appear in an SDLC artifact.

## Verification

Run:

```powershell
python scripts/validate_sdlc_artifact.py
python scripts/validate_sdlc_state_machine.py
python scripts/validate_sdlc_release_readiness.py --strict
python scripts/validate_sdlc_security_review.py --strict
python scripts/validate_sdlc_pr_enforcement.py
python -m pytest tests/test_validate_sdlc_artifact.py tests/test_validate_sdlc_state_machine.py tests/test_validate_sdlc_release_readiness.py tests/test_sdlc_security_review.py -q
python scripts/run_workspace_governance_checks.py
```

## Doctrine

```text
No idea without intake.
No intake without requirement.
No requirement without design.
No design without rollback.
No implementation without tests.
No test without receipt.
No release without evidence.
No deployment without witness.
No claim without proof.
No closure without learning.
```
