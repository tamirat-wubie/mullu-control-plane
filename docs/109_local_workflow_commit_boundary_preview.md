# Local Workflow Commit Boundary Preview

Purpose: define the local staging and commit boundary for the capability-debt
closure and Local Developer Workflow v1 change set before any git mutation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `git status --short`, `git diff --numstat`,
`git ls-files --others --exclude-standard`, and PR readiness handoff packets.
Invariants: this preview does not stage files, create a commit, push a branch,
open a pull request, merge, deploy, call connectors, send email, move money, or
write production state.

## Boundary Verdict

Outcome: `SolvedUnverified`.

Reason: the local file boundary is explicit and locally validated, but no commit
has been created and no remote CI or branch-protection evidence exists yet.

## Branch

```text
codex/capability-debt-closure-runner-20260702
```

## Tracked Modified Files

```text
docs/100_capability_control_system.md
docs/58_general_agent_promotion_operator_runbook.md
docs/74_capability_passports.md
examples/capability_passports.foundation.json
mcoi/mcoi_runtime/app/capability_passports.py
mcoi/pyproject.toml
schemas/capability_passports.schema.json
schemas/mullu_governance_protocol.manifest.json
scripts/plan_capability_adapter_closure.py
scripts/produce_browser_sandbox_evidence.py
scripts/produce_capability_adapter_live_receipts.py
scripts/validate_capability_passports.py
scripts/validate_sandbox_execution_receipt.py
tests/test_plan_capability_adapter_closure.py
tests/test_produce_browser_sandbox_evidence.py
tests/test_general_agent_promotion_operator_runbook.py
tests/test_validate_browser_sandbox_evidence.py
tests/test_validate_capability_passports.py
tests/test_validate_protocol_manifest.py
tests/test_validate_sandbox_execution_receipt.py
```

## New Files To Stage

```text
docs/101_capability_closure_runner.md
docs/102_local_developer_workflow_v1.md
docs/103_patch_proposal_draft.md
docs/104_operator_workflow_dashboard.md
docs/105_safe_local_action_rehearsal.md
docs/106_causal_repair_service.md
docs/107_local_workflow_pr_readiness.md
docs/108_local_workflow_pr_handoff.md
docs/109_local_workflow_commit_boundary_preview.md
examples/capability_closure_plan.foundation.json
examples/closure_receipt.foundation.json
examples/missing_evidence_refs.foundation.json
examples/next_approval_action.foundation.json
gateway/operator_workflow_dashboard.py
mcoi/capability_closure/__init__.py
mcoi/capability_closure/runner.py
mcoi/capability_levels/__init__.py
mcoi/capability_levels/ladder.py
mcoi/causal_repair/__init__.py
mcoi/causal_repair/service.py
mcoi/govern/safe_local_action_rehearsal/__init__.py
mcoi/govern/safe_local_action_rehearsal/runner.py
mcoi/software_dev/local_developer_workflow_v1/__init__.py
mcoi/software_dev/local_developer_workflow_v1/composition.py
mcoi/software_dev/local_developer_workflow_v1/runner.py
mcoi/software_dev/patch_proposal/__init__.py
mcoi/software_dev/patch_proposal/runner.py
schemas/capability_closure_plan.schema.json
schemas/causal_repair_service_receipt.schema.json
schemas/closure_receipt.schema.json
schemas/missing_evidence_refs.schema.json
schemas/next_approval_action.schema.json
schemas/operator_workflow_dashboard_read_model.schema.json
schemas/safe_local_action_rehearsal_receipt.schema.json
schemas/software_dev_patch_proposal.schema.json
scripts/run_capability_debt_closure.py
scripts/run_causal_repair_service.py
scripts/run_local_developer_workflow_v1.py
scripts/run_patch_proposal_draft.py
scripts/run_safe_local_action_rehearsal.py
scripts/run_wsl_browser_sandbox_evidence.py
scripts/validate_capability_closure_runner.py
scripts/validate_causal_repair_service_receipt.py
scripts/validate_local_developer_workflow_v1.py
scripts/validate_patch_proposal_draft.py
scripts/validate_safe_local_action_rehearsal.py
tests/test_capability_closure_runner.py
tests/test_causal_repair_service.py
tests/test_local_developer_workflow_v1.py
tests/test_operator_workflow_dashboard.py
tests/test_patch_proposal_draft.py
tests/test_run_wsl_browser_sandbox_evidence.py
tests/test_safe_local_action_rehearsal.py
tests/test_validate_capability_closure_runner.py
```

## Staging Command Preview

```powershell
git add -- docs/100_capability_control_system.md docs/58_general_agent_promotion_operator_runbook.md docs/74_capability_passports.md examples/capability_passports.foundation.json mcoi/mcoi_runtime/app/capability_passports.py mcoi/pyproject.toml schemas/capability_passports.schema.json schemas/mullu_governance_protocol.manifest.json scripts/plan_capability_adapter_closure.py scripts/produce_browser_sandbox_evidence.py scripts/produce_capability_adapter_live_receipts.py scripts/validate_capability_passports.py scripts/validate_sandbox_execution_receipt.py tests/test_plan_capability_adapter_closure.py tests/test_produce_browser_sandbox_evidence.py tests/test_general_agent_promotion_operator_runbook.py tests/test_validate_browser_sandbox_evidence.py tests/test_validate_capability_passports.py tests/test_validate_protocol_manifest.py tests/test_validate_sandbox_execution_receipt.py docs/101_capability_closure_runner.md docs/102_local_developer_workflow_v1.md docs/103_patch_proposal_draft.md docs/104_operator_workflow_dashboard.md docs/105_safe_local_action_rehearsal.md docs/106_causal_repair_service.md docs/107_local_workflow_pr_readiness.md docs/108_local_workflow_pr_handoff.md docs/109_local_workflow_commit_boundary_preview.md examples/capability_closure_plan.foundation.json examples/closure_receipt.foundation.json examples/missing_evidence_refs.foundation.json examples/next_approval_action.foundation.json gateway/operator_workflow_dashboard.py mcoi/capability_closure/__init__.py mcoi/capability_closure/runner.py mcoi/capability_levels/__init__.py mcoi/capability_levels/ladder.py mcoi/causal_repair/__init__.py mcoi/causal_repair/service.py mcoi/govern/safe_local_action_rehearsal/__init__.py mcoi/govern/safe_local_action_rehearsal/runner.py mcoi/software_dev/local_developer_workflow_v1/__init__.py mcoi/software_dev/local_developer_workflow_v1/composition.py mcoi/software_dev/local_developer_workflow_v1/runner.py mcoi/software_dev/patch_proposal/__init__.py mcoi/software_dev/patch_proposal/runner.py schemas/capability_closure_plan.schema.json schemas/causal_repair_service_receipt.schema.json schemas/closure_receipt.schema.json schemas/missing_evidence_refs.schema.json schemas/next_approval_action.schema.json schemas/operator_workflow_dashboard_read_model.schema.json schemas/safe_local_action_rehearsal_receipt.schema.json schemas/software_dev_patch_proposal.schema.json scripts/run_capability_debt_closure.py scripts/run_causal_repair_service.py scripts/run_local_developer_workflow_v1.py scripts/run_patch_proposal_draft.py scripts/run_safe_local_action_rehearsal.py scripts/run_wsl_browser_sandbox_evidence.py scripts/validate_capability_closure_runner.py scripts/validate_causal_repair_service_receipt.py scripts/validate_local_developer_workflow_v1.py scripts/validate_patch_proposal_draft.py scripts/validate_safe_local_action_rehearsal.py tests/test_capability_closure_runner.py tests/test_causal_repair_service.py tests/test_local_developer_workflow_v1.py tests/test_operator_workflow_dashboard.py tests/test_patch_proposal_draft.py tests/test_run_wsl_browser_sandbox_evidence.py tests/test_safe_local_action_rehearsal.py tests/test_validate_capability_closure_runner.py
```

The command is intentionally a preview. It has not been executed.

## Commit Message Candidate

```text
feat(govern): add capability debt closure workflow

Adds the local capability-debt closure path, Local Developer Workflow v1,
patch proposal mode, safe local action rehearsal, operator workflow dashboard,
causal repair service, and capability promotion ladder projections. The
workflow remains foundation-stage and stops before live execution, branch push,
pull request creation, merge, deployment, connector writes, email sends, money
movement, or production writes. [OCE] [RAG] [CDCV] [CQTE] [UWMA] [SRCA] [PRS]

Tested: focused workflow slice 54 passed; workflow runtime slice 26 passed;
SDLC slice 127 passed; schema validation passed; workspace preflight receipt
validated 331/331 checks passed.
```

## Review Notes

1. Browser sandbox isolation changes are in the same branch surface and should
   be reviewed together unless the operator chooses to split them.
2. `git diff --check` returned exit `0` with line-ending warnings only.
3. The preflight JSON receipt validates as passed even though one full
   preflight shell process returned exit `1` after streaming partial output.
4. No local staging, commit, push, PR creation, or publication has occurred.

STATUS:
  Completeness: 100%
  Invariants verified: explicit file boundary, commit message candidate, no git mutation, no external publication
  Open issues: no local commit exists; remote CI and branch protection remain AwaitingEvidence
  Next action: execute staging and local commit only after explicit operator approval
