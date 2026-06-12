# Branch-protection reconciliation

v21 converts branch-protection policy generation into an auditable reconcile loop.

```text
BranchProtectionPolicy
  + observed branch protection state
  → BranchProtectionReconcilePlan
  → GitHub protected-branch REST payload
  → BranchProtectionReconcileReceipt
```

The reconcile plan records:

```text
repository / branch
observed drift
required actions
PUT /repos/{owner}/{repo}/branches/{branch}/protection
payload hash
mode
```

`apply_approved` mode requires a response payload so the receipt can bind the external GitHub mutation to recorded evidence. `plan_only` and `dry_run` modes remain safe rehearsal paths.
