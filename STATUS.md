<!--
Purpose: Public repository status witness for GitHub-visible state.
Governance scope: Branch, release, CI, and change-assurance reflection.
Dependencies: README.md, RELEASE_CHECKLIST_v0.1.md, .github/workflows/ci.yml,
  scripts/validate_release_status.py.
Invariants: Claims are bounded to named witnesses; gaps are explicit; status
  updates are validated by the release-status gate.
-->

# Repository Status Witness

**Last audited:** 2026-04-24
**Repository:** `tamirat-wubie/mullu-control-plane`
**Default branch:** `main`
**Audited runtime baseline:** `2fdcd37046e0be096ac4c52c357257e4f65c0c0a`
**Audited runtime baseline subject:** `fix(persistence): witness governance store close failures (#305)`
**Status witness publication head:** `3cb270bc4cb1fe9e0c38cb3ced8f2cfca9ac1024`
**Status witness publication subject:** `docs: add repository status witness (#306)`

## Reflection Summary

| Surface | Witness | Status |
|---|---|---|
| Branch witness | GitHub `main` contains this status witness; the audited runtime baseline is named separately from the mutable status-witness commit | Reflected |
| Release witness | GitHub latest release points to `v3.13.0`; release docs declare `0.4.0 (v3.13.0)` | Reflected |
| CI witness | `.github/workflows/ci.yml` contains Python, Rust, schema, artifact, release-status, and change-assurance gates | Reflected |
| Governance witness | `scripts/validate_release_status.py --strict` validates release documents, schemas, artifacts, CI literals, source hygiene, and metadata alignment | Reflected |
| Operational witness | Runtime deployment, live health, and production readiness are not exposed on the repository landing page | Not reflected |

## Required Public Anchors

The GitHub page is sufficient only when these anchors are present and current:

1. README links to this status witness.
2. CI keeps `python scripts/validate_release_status.py --strict`.
3. CI keeps `python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md`.
4. Release metadata in `RELEASE_NOTES_v0.1.md`, `KNOWN_LIMITATIONS_v0.1.md`, and `SECURITY_MODEL_v0.1.md` remains aligned.
5. Known reflection gaps are named instead of implied.

## Known Reflection Gaps

| Gap | Cause | Required closure |
|---|---|---|
| Deployment status absent | GitHub repository page has no live environment health witness | Add deployment badges or a deployment status document once live environments are governed |
| Test-count claim not machine-derived | README states test volume as a human-maintained claim | Derive test inventory from CI or a generated manifest |
| Repository About metadata external to git | GitHub description/topics are not versioned in this repository | Keep the mirrored claim in this witness and automate GitHub metadata checks |

## Proof Chain

| Check | Command |
|---|---|
| Branch freshness | `git status --short --branch` |
| Remote head | `git ls-remote origin refs/heads/main` |
| Release status | `python scripts/validate_release_status.py --strict` |
| Change assurance | `python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md` |

