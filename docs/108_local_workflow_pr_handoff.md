# Local Workflow PR Handoff

Purpose: provide the operator-ready PR handoff for the capability-debt closure
and Local Developer Workflow v1 change set.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: local git status, SDLC readiness validators, workspace preflight
receipt, focused tests, and `docs/107_local_workflow_pr_readiness.md`.
Invariants: this handoff does not stage files, create commits, push branches,
open pull requests, merge, deploy, call connectors, send email, move money, or
write production state.

## Release Surface

```text
branch: codex/capability-debt-closure-runner-20260702
release target: draft pull request to main
audience: Mullusi operator and repository reviewers
publication status: not published
remote CI status: AwaitingEvidence
```

## Commit Boundary

No commit has been created in this handoff step. The current boundary is the
workspace diff and untracked inventory observed by:

```powershell
git status --short
git diff --name-only
git ls-files --others --exclude-standard
```

Tracked modified files:

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

Untracked new files:

```text
docs/101_capability_closure_runner.md
docs/102_local_developer_workflow_v1.md
docs/103_patch_proposal_draft.md
docs/104_operator_workflow_dashboard.md
docs/105_safe_local_action_rehearsal.md
docs/106_causal_repair_service.md
docs/107_local_workflow_pr_readiness.md
docs/108_local_workflow_pr_handoff.md
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

## Import And Dependency Impact

New Python package surfaces:

```text
mcoi/capability_closure
mcoi/capability_levels
mcoi/causal_repair
mcoi/govern/safe_local_action_rehearsal
mcoi/software_dev/local_developer_workflow_v1
mcoi/software_dev/patch_proposal
```

Dependency impact:

```text
No third-party dependency install was performed.
mcoi/pyproject.toml changed to include new local package coverage.
New imports are repository-local gateway, scripts, mcoi_runtime, and package modules.
```

## Constructive Deltas

1. Capability debt can now be closed through a ranked, approval-bound runner.
2. Local Developer Workflow v1 now produces repo status, patch plan, diff
   proposal, test plan, receipt, approval request, and PR command preview.
3. Patch Proposal Mode provides value before file mutation.
4. Operator Workflow Dashboard unifies task, gate, evidence, receipt, rollback,
   approval, and promotion-level filters.
5. Safe Local Action Rehearsal simulates local and external actions without
   mutation.
6. Causal Repair Service classifies repair paths for failed or missing evidence.
7. Capability passports expose L0-L9 promotion levels as non-authoritative
   read-model classifications.
8. Local Developer Workflow v1 has a governed composition descriptor that halts
   at a terminal wait stage before external execution.

## Fracture Deltas

None intentional.

## Residual Risks

1. Remote CI and branch-protection evidence are unavailable until a draft PR is
   opened.
2. The full workspace preflight process returned shell exit code `1` in one
   run, while the saved JSON receipt validated as `passed` with `331` checks and
   `0` failures.
3. Browser sandbox isolation changes are present in the same worktree; reviewers
   should treat them as part of this PR unless the operator chooses to split the
   branch.

## Rollback And Compensation

Rollback is local repository rollback only:

```text
remove new docs, examples, modules, schemas, scripts, and tests
restore modified tracked files from the branch base
discard .tmp and .change_assurance generated receipts if not needed for review
```

No production rollback, connector compensation, payment reversal, customer
notice, or deployment rollback is required because no external state changed.

## Observed Validation

```text
git diff --check
exit: 0
notes: line-ending warnings only
```

```text
python scripts/validate_sdlc_artifact.py
STATUS: passed

python scripts/validate_sdlc_state_machine.py
STATUS: passed

python scripts/validate_sdlc_release_readiness.py --strict
STATUS: passed

python scripts/validate_sdlc_security_review.py --strict
STATUS: passed

python scripts/validate_sdlc_pr_enforcement.py
STATUS: passed

python scripts/validate_sdlc_route.py
STATUS: passed
```

```text
python -m pytest tests/test_validate_sdlc_artifact.py tests/test_validate_sdlc_state_machine.py tests/test_validate_sdlc_release_readiness.py tests/test_sdlc_security_review.py tests/test_validate_sdlc_pr_enforcement.py tests/test_validate_sdlc_route.py -q
127 passed
```

Additional evidence is retained in:

```text
docs/107_local_workflow_pr_readiness.md
.tmp/workspace-governance-preflight-receipt.json
```

## Draft PR Body

```markdown
## Summary
Adds the governed local developer workflow closure path for Mullusi capability debt, including closure planning, patch proposal, safe action rehearsal, operator dashboard projection, causal repair, and promotion-level visibility.

### Governance Scope
- Laws verified: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
- Phi traversal layers touched: 1-13 through workflow, governance, execution, feedback, and evolution surfaces
- Invariants preserved: no live execution, no PR creation, no branch push, no merge, no deployment, no connector write
- Invariants modified: none

### Changes
- Constructive deltas: capability closure runner, Local Developer Workflow v1, patch proposal mode, operator dashboard, safe action rehearsal, causal repair service, capability promotion ladder, governed composition descriptor
- Fracture deltas: none intentional

### Testing
- Tests added/modified: focused capability closure, local workflow, patch proposal, dashboard, rehearsal, causal repair, promotion ladder, browser sandbox, and SDLC tests
- Assertions passing: focused workflow slice 54 passed; workflow runtime slice 26 passed; SDLC slice 127 passed
- Edge cases covered: authority overclaim rejection, link drift, terminal wait drift, schema drift, promotion overclaim, missing evidence classification
- Warnings: git line-ending warnings only

### Status
- [x] Local governance validators passing
- [x] Workspace preflight receipt validates as passed
- [x] No live execution authority introduced
- [x] Rollback path documented
- [ ] Remote CI observed
- [ ] Branch protection observed

### Next Action
Open a draft PR only after operator approval, then wait for remote CI and branch-protection evidence.
```

## Selected Release Action

```text
prepare_draft_pr_after_operator_approval
```

Publication is blocked until explicit operator approval for push and PR
creation.

STATUS:
  Completeness: 100%
  Invariants verified: local handoff packet, observed changed-file inventory, rollback boundary, no publication
  Open issues: remote CI AwaitingEvidence; no commit boundary yet; push and PR creation blocked pending operator approval
  Next action: stage and commit locally only after operator approval; push/open draft PR only after separate explicit approval
