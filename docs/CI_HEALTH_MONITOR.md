Purpose: document the repository-local CI health monitor.
Governance scope: CI sensing, PR readiness triage, and mainline workflow witness review.
Dependencies: GitHub CLI authentication, `scripts/report_ci_health.py`, GitHub Actions check metadata.
Invariants: monitor is read-only, emits bounded metadata only, and does not print secrets or logs.

# CI Health Monitor

`scripts/report_ci_health.py` gives the operator one bounded CI health view before merge or release work continues.

It checks:

1. Open pull requests and their check rollups.
2. Latest `main` workflow run per workflow.
3. Failed or unsettled checks.
4. Non-clean PR merge state as a warning.

Run:

```powershell
python scripts/report_ci_health.py
```

JSON output:

```powershell
python scripts/report_ci_health.py --json
```

Failure rules:

- Exit `0`: no failed or pending CI evidence.
- Exit `1`: failed or pending CI evidence exists.
- Exit `2`: GitHub CLI collection failed or returned malformed data.

The monitor is a sensing tool only. It does not dispatch workflows, merge PRs, mutate branches, download logs, read secrets, or alter GitHub state.

STATUS:
  Completeness: 100%
  Invariants verified: read-only collection, bounded metadata, no secret/log output, deterministic evaluator
  Open issues: live output depends on GitHub CLI authentication
  Next action: run before merge or release closure
