# Workflow Run Contract

Purpose: define the canonical causal workflow-run lifecycle for governed Mullusi work.
Governance scope: WorkflowRun schema, validator, fixture, runtime projection, receipts, rollback, and monitoring.
Dependencies: `schemas/workflow_run.schema.json`, `scripts/validate_workflow_run.py`, and `gateway/workflow_orchestration.py`.
Invariants: no false success, no high-risk execution without approval, no external effect without rollback readiness, no terminal closure without receipts.

## Architecture

`WorkflowRun` is the runtime organizing kernel for a governed task. It binds the request, intent, boundary, risk class, action plan, evidence, approval, execution state, rollback posture, validation result, receipts, and monitoring state into one auditable object.

The contract preserves the existing gateway task graph while adding the causal lifecycle fields required for cross-domain operation.

## Lifecycle States

| State | Meaning |
| --- | --- |
| `INTAKE` | Request captured but not interpreted. |
| `INTERPRETED` | Intent model formed. |
| `BOUNDARY_CHECKED` | Scope, permission, and protected zones recorded. |
| `EVIDENCE_ASSEMBLED` | Evidence refs attached and graded outside this schema. |
| `RISK_CLASSIFIED` | Risk class assigned. |
| `PLANNED` | Action plan exists, execution not started. |
| `AWAITING_APPROVAL` | Approval is required before progression. |
| `APPROVED` | Approval refs permit bounded progression. |
| `EXECUTING` | Controlled execution is active. |
| `OBSERVED` | Result has been measured. |
| `VALIDATED` | Validation result is attached. |
| `RECEIPTED` | Receipt refs are attached before terminal closure. |
| `CLOSED` | Goal is validated, receipts exist, rollback state is known. |
| `BLOCKED` | A hard gate needs evidence or operator decision. |
| `FAILED` | Workflow failed without closure. |
| `ROLLED_BACK` | Failure was compensated or reversed with evidence. |

## Risk Classes

| Class | Meaning | Gate |
| --- | --- | --- |
| `R0` | Explanation only | No approval by default. |
| `R1` | Draft or read-only action | Fast path with receipt. |
| `R2` | Reversible local action | Evidence and rollback posture required. |
| `R3` | Externally visible action | Approval, rollback, receipt, and monitoring required. |
| `R4` | High-impact, destructive, financial, legal, or production action | Strong approval and rollback or compensation required. |
| `R5` | Prohibited action | Must remain `BLOCKED` or `FAILED`. |

## Validation Rules

1. R0/R1 read-only runs may close without approval only when evidence and receipt refs exist.
2. R3/R4 runs cannot enter `APPROVED`, `EXECUTING`, `OBSERVED`, `VALIDATED`, `RECEIPTED`, `CLOSED`, or `ROLLED_BACK` without `approval_refs`.
3. External effects require `rollback_required = true`, `rollback_ready = true`, a known reversibility label, rollback refs or a compensating action, and monitoring.
4. `CLOSED` requires `validation_result.status = PASS` plus true values for goal satisfaction, constraint respect, evidence attachment, receipt emission, rollback-state knowledge, and monitoring handling.
5. Terminal states require `receipt_refs`.

## Verification

Run the focused validator:

```powershell
python scripts/validate_workflow_run.py
python -m pytest tests/test_validate_workflow_run.py -q
```

The canonical fixture is:

```text
examples/workflow_run_governed_work_assistant_demo_v0.foundation.json
```
