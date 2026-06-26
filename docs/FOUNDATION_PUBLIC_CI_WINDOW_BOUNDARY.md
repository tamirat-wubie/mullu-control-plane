# Foundation Public CI Window Boundary

Purpose: govern temporary repository-public windows used only as a GitHub
Actions execution surface during Foundation Mode budget constraints.
Governance scope: source-control visibility, GitHub Actions execution,
proprietary boundary protection, CI evidence, post-window receipts, and
public-readiness separation.
Dependencies: GitHub repository visibility controls, GitHub Actions, public
repository surface validation, proprietary boundary validation, CI health
reporting, and Foundation Mode posture.
Invariants: public visibility is not public readiness; no raw secrets are
printed or committed; public windows do not authorize customer exposure,
production deployment, public launch, legal filing, fundraising, or support
commitments.

## Boundary

The public CI window is a temporary CI execution surface. It exists because a
private repository may not have enough available Actions budget. The window
permits bounded GitHub Actions execution and repository metadata validation
only. It does not change Foundation Mode, does not create public readiness, and
does not promote any public launch claim.

## Allowed Actions

1. Run repository-local governance, test, release, public-surface, and
   proprietary-boundary checks through GitHub Actions.
2. Push governed branches or pull requests needed to obtain CI evidence.
3. Read check status, CI logs, and repository metadata needed for verification.
4. Record a post-window receipt that explains why the window opened, what ran,
   what failed or passed, and how the exposure was closed or bounded.

## Blocked Actions

1. Treat public visibility as public readiness.
2. Announce public launch, customer access, production deployment, compliance
   certification, legal clearance, fundraising readiness, or commercial
   availability from a CI window alone.
3. No raw secrets are printed or committed. Do not copy or expose raw secrets, private keys, access tokens, or
   credentials.
4. Widen repository exposure beyond the minimum time needed to run and inspect
   Actions.
5. Use public visibility to bypass Foundation Mode, proprietary boundary
   checks, or Life-Meaning governance.

## Required Window Phases

| Phase | Required decision | Required evidence |
| --- | --- | --- |
| pre-window | Confirm the window is needed for CI budget or Actions access. | Local check plan, target branch, target commit, and expected workflows. |
| open-window | Make the repository public only for bounded Actions execution. | Visibility timestamp, actor, reason, and branch or pull request reference. |
| execution-window | Run and observe GitHub Actions without publishing new readiness claims. | Workflow run URLs, commit SHA, pass/fail state, and relevant logs. |
| close-window | Make the repository private again when possible, or record why it remains public. | Closure timestamp or explicit bounded exposure decision. |
| post-window receipt | Preserve a UWMA record of the window. | Receipt fields listed below. |

## Required Validators

Before and after a public CI window, run the strongest available local lanes:

```powershell
python scripts/validate_public_repository_surface.py --local-only
python scripts/validate_proprietary_boundary.py
python scripts/validate_release_status.py
python scripts/report_ci_health.py --repo tamirat-wubie/mullu-control-plane --branch main --json
```

When the repository is public and live metadata is intentionally available, the
remote surface check may also run:

```powershell
python scripts/validate_public_repository_surface.py
```

## Receipt Contract

A public CI window receipt must include:

| Field | Meaning |
| --- | --- |
| window_id | Stable identifier for the window. |
| reason | Budget or Actions access reason for opening visibility. |
| repo_visibility_before | Visibility before opening the window. |
| repo_visibility_after | Visibility after closing or bounding the window. |
| opened_at | Timestamp for public visibility start, if known. |
| closed_at | Timestamp for private restoration, or null with bounded reason. |
| branch | Branch or pull request being verified. |
| head_sha | Commit SHA under CI verification. |
| workflow_run_urls | GitHub Actions runs observed during the window. |
| validators | Local and remote validator commands with pass, fail, or AwaitingEvidence. |
| exposure_decision | Why remaining public exposure is acceptable or why it was closed. |
| closure_decision | Next private, public, or AwaitingEvidence action. |

The committed AwaitingEvidence witness is
[`../examples/foundation_public_ci_window_boundary_witness.awaiting_evidence.json`](../examples/foundation_public_ci_window_boundary_witness.awaiting_evidence.json).
It is a template-level boundary witness only. It does not claim that any live
public CI window is currently open, closed, or deployment-ready.

## Status

- Solver outcome: AwaitingEvidence for public readiness.
- Public CI window outcome: SolvedVerified only when validators, CI evidence,
  and post-window receipt agree.
- Next action: keep the repository public only as long as the CI window requires,
  then close or reclassify exposure with an explicit receipt.

```powershell
python scripts/validate_foundation_public_ci_window_boundary.py
```

STATUS:
  Completeness: 100%
  Invariants verified: public visibility is not public readiness; no raw secrets; no customer exposure; no production deployment claim; Foundation Mode remains active
  Open issues: live public CI windows still require a window-specific receipt
  Next action: run the validator and record a post-window receipt for any live visibility change
