# Local Workflow PR Readiness Packet

Purpose: capture local PR readiness evidence for the capability-debt closure,
local developer workflow, patch proposal, dashboard, rehearsal, causal repair,
and promotion ladder change set.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: SDLC validators, focused test suites, workspace governance
preflight receipt, and the local workflow documentation set.
Invariants: this packet is evidence and review material only; it does not
stage files, create commits, push branches, open pull requests, merge, deploy,
call connectors, send email, move money, or write production state.

## Readiness Verdict

Outcome: `SolvedUnverified`.

Reason: local SDLC validators, focused tests, schema validation, and workspace
preflight receipt pass. Remote PR CI and branch-protection checks remain
unobserved because no pull request was opened by this workflow.

## Constructive Deltas

1. Added Capability Debt Closure Runner artifacts and validation.
2. Added Local Developer Workflow v1 preview artifacts.
3. Added Patch Proposal Mode before file mutation.
4. Added Operator Workflow Dashboard with promotion ladder filters.
5. Added Safe Local Action Rehearsal.
6. Added Causal Repair Service.
7. Added Capability Promotion Ladder in capability passports.
8. Added governed foundation composition for the complete local workflow chain.

## Fracture Deltas

None intentional.

## Changed Surfaces

```text
docs/
examples/
gateway/
mcoi/capability_closure/
mcoi/capability_levels/
mcoi/causal_repair/
mcoi/govern/
mcoi/software_dev/
schemas/
scripts/
tests/
```

Existing browser sandbox isolation files are also present in the worktree and
must remain part of the reviewed PR surface unless the operator explicitly
splits them into a separate branch.

## Verification Evidence

```powershell
python -m pytest tests/test_local_developer_workflow_v1.py -q
# 9 passed

python -m pytest tests/test_validate_capability_passport_dashboard.py tests/test_validate_capability_passports.py tests/test_capability_closure_runner.py tests/test_validate_capability_closure_runner.py tests/test_local_developer_workflow_v1.py tests/test_patch_proposal_draft.py tests/test_operator_workflow_dashboard.py tests/test_safe_local_action_rehearsal.py tests/test_causal_repair_service.py -q
# 54 passed

python -m pytest mcoi/tests/test_workflow_runtime_integration.py mcoi/tests/test_capability_unlock_ladder.py -q
# 26 passed

python -m pytest tests/test_validate_sdlc_artifact.py tests/test_validate_sdlc_state_machine.py tests/test_validate_sdlc_release_readiness.py tests/test_sdlc_security_review.py tests/test_validate_sdlc_pr_enforcement.py tests/test_validate_sdlc_route.py -q
# 127 passed

python scripts/validate_schemas.py
# all checks passed

python scripts/validate_sdlc_artifact.py
python scripts/validate_sdlc_state_machine.py
python scripts/validate_sdlc_release_readiness.py --strict
python scripts/validate_sdlc_security_review.py --strict
python scripts/validate_sdlc_pr_enforcement.py
python scripts/validate_sdlc_route.py
# all passed

python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt.json
# STATUS: passed
```

Workspace preflight receipt:

```text
.tmp/workspace-governance-preflight-receipt.json
status: passed
check_count: 331
failed_count: 0
```

The full preflight command returned shell exit code `1` during one run after
streaming partial check output, but the saved receipt validated as complete and
passed with `331` checks and `0` failures.

## Rollback Path

No external state was changed by the workflow.

Rollback is repository-local:

```text
remove added local workflow modules, schemas, scripts, tests, docs, and examples
restore modified capability passport, manifest, and browser sandbox files from the branch base
discard generated .tmp/.change_assurance receipts if not needed for review
```

No production rollback, connector compensation, customer notification, payment
reversal, or deployment rollback is required.

## Security And Authority Boundary

Blocked effects remain:

```text
file_write beyond explicit repository edits
branch_push
pull_request_create
merge
deploy
connector_call
send_email
move_money
write_production_data
```

Promotion ladder levels are read-model classifications, not execution
authority. The operator dashboard requires `external_effects_allowed=false`
and `live_execution_enabled=false`.

## PR Summary Draft

Summary: Adds the governed local developer workflow closure path for Mullusi
capability debt, including closure planning, patch proposal, safe action
rehearsal, dashboard projection, causal repair, and promotion-level visibility.

Governance scope:

```text
Laws verified: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Phi traversal layers touched: 1-13 via workflow, governance, execution, feedback, and evolution surfaces
Invariants preserved: no live execution, no PR creation, no branch push, no merge, no deployment, no connector write
Invariants modified: none
```

Testing:

```text
Focused workflow tests: 54 passed
Workflow runtime tests: 26 passed
SDLC tests: 127 passed
Workspace preflight receipt: 331/331 passed
Warnings: line-ending warnings from git diff --check only
```

## Remaining Evidence

Remote CI and branch-protection observations are `AwaitingEvidence` until a PR
exists and GitHub checks run.

STATUS:
  Completeness: 100%
  Invariants verified: local SDLC validators, focused tests, schema validation, workspace preflight receipt, no live execution authority
  Open issues: remote CI not observed because no PR was opened; full preflight shell exit mismatch despite passed saved receipt
  Next action: stage reviewed files, commit, push, and open a draft PR only after operator approval
