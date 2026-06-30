<!--
Purpose: record the repository boundary after the 2026-06-29 deployment extraction confusion.
Governance scope: canonical repository identity, deployment extraction boundary, local checkout selection, and push-safety checks.
Dependencies: GitHub repository metadata, local Git remotes, Render deployment repositories, scripts/check_repository_boundary.py.
Invariants: no histories are merged; full-platform work stays in the canonical repository unless a governed migration is approved.
-->

# Repository Boundary 2026-06-29

## Boundary Decision

The canonical full-platform repository is:

```text
tamirat-wubie/mullu-control-plane
```

The deployment extraction repository is:

```text
mullusi/mullusi-control-plane
```

These repositories have unrelated Git histories and must not be merged as if
they were branches of one repository.

## Current Roles

| Repository | Role | Boundary |
| --- | --- | --- |
| `tamirat-wubie/mullu-control-plane` | Canonical full platform | Contains `gateway`, `governance`, `capabilities`, `mcoi`, `maf`, release notes, and governed deployment evidence. |
| `mullusi/mullusi-control-plane` | Public deployment extraction for now | Contains a small `apps/api` and `apps/dashboard` surface used during Render deployment hardening. It is intentionally public for the current phase and must not contain production secrets. |

## Local Checkout Rule

Use this checkout for full-platform development:

```text
C:\Users\tmrtl\Projects\Agentic framwork and computer uses inteligence\mullu-control-plane
```

Do not use this checkout for full-platform development:

```text
D:\mullusi-control-plane
```

That `D:\` checkout points to the deployment extraction repository.

## Guard Command

Before pushing full-platform work, run:

```powershell
python scripts/check_repository_boundary.py
```

Expected canonical result:

```text
repository_boundary=canonical
canonical_repo=tamirat-wubie/mullu-control-plane
```

If the guard reports `deployment_extraction`, stop and switch to the canonical
checkout before continuing.

## Porting Rule

Changes from `mullusi/mullusi-control-plane` may be ported only as intentional
bounded deltas. Do not merge unrelated histories. Do not copy the extracted
`apps/api` and `apps/dashboard` tree into this repository unless a separate
architecture decision proves it belongs here.

## Rollback

If future work lands in the deployment extraction repository by mistake:

1. Stop pushing from that checkout.
2. Record the mistaken branch and commit SHAs.
3. Create a fresh branch in the canonical repository.
4. Port only the minimal files or concepts that match the canonical gateway and
   governance architecture.
5. Leave the deployment extraction history intact; do not rewrite it without a
   separate operator approval.
