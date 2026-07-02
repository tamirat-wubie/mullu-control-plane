# Local Developer Workflow v1

Purpose: define the first local-lab developer workflow bundle that turns a repo
task into patch planning, diff proposal, test plan, receipt, approval request,
and PR command preview without source or external mutation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `mcoi/software_dev/local_developer_workflow_v1/runner.py`,
`mcoi/software_dev/local_developer_workflow_v1/composition.py`,
`scripts/run_local_developer_workflow_v1.py`, and
`scripts/validate_local_developer_workflow_v1.py`.
Invariants: no file write, branch push, PR creation, merge, deployment,
connector call, or live execution authority is granted.

## Workflow

```text
repo status
-> patch plan draft
-> diff proposal
-> test plan
-> receipt
-> approval request
-> PR command preview
```

## Governed Composition

The foundation composition descriptor binds this workflow to the adjacent
closure and governance services:

```text
capability closure lane
-> patch proposal draft
-> local workflow preview bundle
-> safe local action rehearsal
-> operator dashboard projection
-> causal repair classification
-> operator review gate
-> wait for separate external execution approval
```

Canonical builder:

```text
build_foundation_workflow_composition_descriptor()
build_foundation_workflow_composition_read_model()
validate_foundation_workflow_composition()
```

Terminal closure is intentionally a `wait_for_event` stage:

```text
await_external_execution_approval
```

This stage prevents the composition from silently crossing into branch push,
PR creation, merge, deployment, connector calls, email sends, money movement,
or production writes.

## Artifacts

| Artifact | Role |
| --- | --- |
| `local_developer_workflow_v1_repo_status.json` | Read-only local git status projection. |
| `local_developer_workflow_v1_patch_plan.json` | Draft-only patch plan and causal receipt. |
| `local_developer_workflow_v1_diff_proposal.json` | Preview-only diff proposal; not applied. |
| `local_developer_workflow_v1_test_plan.json` | Commands to run later; not executed by this workflow. |
| `local_developer_workflow_v1_receipt.json` | Causal trace for the whole local bundle. |
| `local_developer_workflow_v1_approval_request.json` | Operator review packet; no execution authority. |
| `local_developer_workflow_v1_pr_command_preview.json` | Push and PR command text with execution blocked. |

## Commands

```powershell
python scripts/run_local_developer_workflow_v1.py --json --strict
python scripts/validate_local_developer_workflow_v1.py --json --strict
python -m pytest tests/test_local_developer_workflow_v1.py -q
```

## Boundaries

All generated artifacts keep:

```text
file_write_performed = false
branch_push_performed = false
pull_request_created = false
merge_performed = false
deployment_performed = false
connector_call_performed = false
live_execution_enabled = false
```

STATUS:
  Completeness: 100%
  Invariants verified: preview-only artifacts, explicit approval boundary, terminal wait before external execution, no source mutation, no external effect
  Open issues: none
  Next action: review the full local developer workflow change set for PR readiness
