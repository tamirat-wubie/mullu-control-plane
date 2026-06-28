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

Bounded-public receipts with an `opened_at` timestamp and no `closed_at`
must close or refresh evidence within six hours. Older open windows are stale
and must not be treated as governed closure evidence.

## Required Validators

Before and after a public CI window, run the strongest available local lanes:

```powershell
python scripts/validate_public_repository_surface.py --local-only
python scripts/validate_proprietary_boundary.py
python scripts/validate_release_status.py
python scripts/report_ci_health.py --repo tamirat-wubie/mullu-control-plane --branch main --json
```

For an operator-facing command packet that does not change visibility by
itself, generate the no-execute checklist:

```powershell
python scripts/generate_public_ci_window_operator_commands.py --pull-request 2380 --branch codex/public-ci-window-visibility-restoration-20260628 --head-sha 331adc8c851b48a754643a9ac33c706c9365071c
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
| repo_visibility_restored | Whether repository visibility was restored to private for a closed window. |
| repo_visibility_restored_at | Timestamp for private visibility restoration, or null while bounded public evidence remains unresolved. |
| opened_at | Timestamp for public visibility start, if known. |
| closed_at | Timestamp for private restoration, or null with bounded reason. |
| branch | Branch or pull request being verified. |
| branch_deleted | Whether the temporary topic branch was deleted after merge or closure. |
| head_sha | Commit SHA under CI verification. |
| merge_commit | Merge commit SHA for a closed pull-request window, or null while bounded public evidence remains unresolved. |
| merged_at | Pull request merge timestamp for a closed window, or null while bounded public evidence remains unresolved. |
| workflow_run_urls | GitHub Actions runs observed during the window. |
| validators | Local and remote validator commands with pass, fail, or AwaitingEvidence. |
| exposure_decision | Why remaining public exposure is acceptable or why it was closed. |
| closure_decision | Next private, public, or AwaitingEvidence action. |

The committed AwaitingEvidence witness is
[`../examples/foundation_public_ci_window_boundary_witness.awaiting_evidence.json`](../examples/foundation_public_ci_window_boundary_witness.awaiting_evidence.json).
It is a template-level boundary witness only. It does not claim that any live
public CI window is currently open, closed, or deployment-ready.

The committed closed receipt example is
[`../examples/foundation_public_ci_window_receipt.closed.example.json`](../examples/foundation_public_ci_window_receipt.closed.example.json).
It records the minimum post-window shape for a CI-only visibility window: PR
URL, branch, commit SHA, workflow run URLs, local validator states, visibility
before/after labels, false public-readiness flags, false secret-exposure flags,
and closure decision. Future live receipts may replace the example values only
when the observed window evidence is available.

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
