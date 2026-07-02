# Patch Proposal Draft

Purpose: define `software_dev.github_patch_proposal.draft`, the reusable
middle layer between patch planning and file writing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `mcoi/software_dev/patch_proposal/runner.py`,
`schemas/software_dev_patch_proposal.schema.json`,
`scripts/run_patch_proposal_draft.py`, and
`scripts/validate_patch_proposal_draft.py`.
Invariants: proposal artifacts are preview-only and cannot apply diffs, run
tests, write files, push branches, open pull requests, merge, deploy, call
connectors, or perform live execution.

## Output

```text
files likely to change
patch objective
safe diff preview
test plan
rollback plan
risk level
approval needed
```

## Commands

```powershell
python scripts/run_patch_proposal_draft.py --json --strict
python scripts/validate_patch_proposal_draft.py --json --strict
python -m pytest tests/test_patch_proposal_draft.py -q
```

STATUS:
  Completeness: 100%
  Invariants verified: preview-only diff, no file write, no branch push, no PR create, approval is review-only
  Open issues: none
  Next action: attach patch proposal summaries to the operator workflow dashboard
