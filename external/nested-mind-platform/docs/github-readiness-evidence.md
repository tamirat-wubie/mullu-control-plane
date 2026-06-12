# GitHub readiness evidence

v20 adds a deterministic evidence model for GitHub pull-request and check-run data.

```text
GitHubPullRequestEvidence
  + GitHubCheckRunEvidence[]
  + required check names
  → GitHubReadinessEvidenceBundle
  → ImplementationEvidenceArtifact[]
```

The bundle is hash-bound and records:

```text
repository
pull request number
head sha
required checks
missing required checks
failing required checks
status
```

Status rules:

```text
satisfied   all required checks are completed with success/neutral/skipped and PR is not draft
incomplete  draft PR or missing required checks
rejected    required check exists but failed/cancelled/timed out/action-required
```

The connector crate now includes `GitHubEvidenceHttpClient`, which can retrieve pull-request metadata and commit check-runs from the GitHub REST API and convert them into kernel evidence objects. The kernel itself remains deterministic and only accepts evidence objects or connector receipts.

CLI rehearsal:

```bash
cargo run -p mind-cli -- github-evidence-demo \
  mullusi/nested-mind-platform \
  20 \
  demo-head-sha
```

API:

```text
GET  /system/github/readiness-evidence
POST /system/github/readiness-evidence
```
