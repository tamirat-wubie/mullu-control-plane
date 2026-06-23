# Branch Cleanup Allowlist Runbook

Date: 2026-06-23

Purpose: define a governed local-branch cleanup policy for the canonical control-plane checkout.

Scope: local Git branch references and local Git worktree bindings only. This runbook does not authorize deleting remote branches, files, worktrees, commits, tags, or release evidence.

Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.

Invariants:

- Never delete a branch that is checked out by any worktree.
- Never delete `main`, `backup/*`, `wip/*`, `local/*`, or `pr-*` branches through the automatic lane.
- Never delete a branch with an `ahead` marker through the automatic lane.
- Never use force deletion for the automatic lane. Use `git branch -d` only.
- Treat no-upstream branches as manual-review candidates, even when Git reports them merged.
- Keep remote branch deletion out of scope unless a separate GitHub witness authorizes it.

## Current Inventory Snapshot

Collected from the canonical checkout after fetching `origin --prune`.

| Metric | Count |
| --- | ---: |
| Open GitHub PRs | 0 |
| Local branches | 1335 |
| Branches merged into `origin/main` | 572 |
| Branches with deleted upstream | 677 |
| Branches with no upstream | 119 |
| Branches tracking `origin/main` | 155 |
| Branches tracking live non-main remotes | 384 |
| Branches with `ahead` marker | 85 |
| Worktrees | 142 |
| Branch-backed worktrees | 124 |
| Detached worktrees | 18 |
| Strict deleted-upstream cleanup candidates | 235 |
| Deleted-upstream merged branches blocked by policy | 15 |
| No-upstream merged manual-review candidates | 46 |

## Automatic Cleanup Lane

A local branch is eligible for automatic cleanup only if every condition is true:

1. It is merged into `origin/main`.
2. Its upstream tracking branch is gone.
3. It is not checked out by any worktree.
4. It is not the current branch.
5. It is not named `main`.
6. It does not match `backup/*`, `wip/*`, `local/*`, or `pr-*`.
7. Its tracking marker does not contain `ahead`.

Automatic cleanup must use `git branch -d`, not `git branch -D`.

## Manual Review Lane

Manual review is required for any branch where one or more of these conditions is true:

- The branch has no upstream.
- The branch has an `ahead` marker.
- The branch is attached to a worktree.
- The branch name is a backup, WIP, local, PR-restack, or operator checkpoint branch.
- The branch tracks a live non-main remote.
- The branch is not merged into `origin/main`.

Manual review requires recording the branch purpose, upstream state, merge evidence, worktree state, and rollback path before deletion.

## Evidence Commands

Use these commands from the canonical checkout.

```powershell
git fetch origin --prune
git status --short --branch
gh pr list --repo tamirat-wubie/mullu-control-plane --state open --limit 100
git worktree list --porcelain
git worktree prune --dry-run --verbose
git branch --merged origin/main --format='%(refname:short)'
git for-each-ref refs/heads --format='%(refname:short)|%(upstream:short)|%(upstream:track)|%(committerdate:iso8601)|%(objectname:short)|%(subject)'
```

## Candidate Generation

This command emits the strict automatic cleanup candidates without deleting them.

```powershell
$merged = @{}
git branch --merged origin/main --format='%(refname:short)' | ForEach-Object { $merged[$_] = $true }

$worktreeBranches = @{}
git worktree list --porcelain | ForEach-Object {
  if ($_ -match '^branch refs/heads/(.+)$') { $worktreeBranches[$Matches[1]] = $true }
}

git for-each-ref refs/heads --format='%(refname:short)|%(upstream:short)|%(upstream:track)|%(committerdate:iso8601)|%(objectname:short)|%(subject)' |
  ForEach-Object {
    $parts = $_ -split '\|', 6
    $name = $parts[0]
    $track = $parts[2]
    $isProtectedName = $name -match '^(main|backup/|wip/|local/|pr-)'

    if (
      $track -eq '[gone]' -and
      $merged.ContainsKey($name) -and
      -not $worktreeBranches.ContainsKey($name) -and
      -not $isProtectedName -and
      -not ($track -match 'ahead')
    ) {
      $name
    }
  }
```

## Deletion Procedure

Deletion must be a separate explicit action after the candidate list is reviewed.

```powershell
$candidates = @(
  # reviewed branch names only
)

foreach ($branch in $candidates) {
  git branch -d -- $branch
}
```

If `git branch -d` refuses a branch, stop and classify the branch under manual review. Do not retry with force deletion in the automatic lane.

## Rollback Path

Before deletion, retain the candidate list with each branch head object ID from:

```powershell
git for-each-ref refs/heads --format='%(refname:short)|%(objectname)'
```

A deleted local branch can be restored with:

```powershell
git branch <branch-name> <object-id>
```

## Closure Criteria

Cleanup is `SolvedVerified` only when:

- every deleted branch was listed in the reviewed candidate set;
- deletion used `git branch -d`;
- `git status --short --branch` is clean afterward;
- `git worktree list --porcelain` shows no deleted branch still attached;
- a rollback map of branch names to object IDs was retained.
