<!--
Purpose: Public deployment-health witness for GitHub-visible state.
Governance scope: runtime endpoint publication, health evidence, and closure
  obligations for production deployment reflection.
Dependencies: STATUS.md, GITHUB_SURFACE.md, DEPLOYMENT.md, RUNBOOK.md.
Invariants: Absence of live deployment evidence is explicit; no production health
  claim is made without named endpoint evidence.
-->

# Deployment Status Witness

**Last audited:** 2026-04-24
**Deployment witness state:** `not-published`
**Public production health endpoint:** `not-declared`
**Gateway health endpoint:** `not-declared`
**API health endpoint:** `not-declared`

## Reflection Summary

| Surface | Witness | Status |
|---|---|---|
| Local API health contract | `RUNBOOK.md` and `DEPLOYMENT.md` document `/health` checks | Reflected |
| Local gateway health contract | `README.md` documents `http://localhost:8001/health` | Reflected |
| Public production health | No governed production endpoint is declared in this repository | Not reflected |
| Deployment badge | No GitHub-visible deployment badge is declared | Not reflected |

## Closure Requirements

Before this witness can claim public deployment health, the repository must name:

1. Production API base URL.
2. Production gateway base URL.
3. Health endpoint response contract.
4. Last successful health-check timestamp.
5. Operator or automation identity that produced the health witness.
6. Failure handling path for stale or unavailable health evidence.

## Proof Chain

| Check | Command |
|---|---|
| Public surface validation | `python scripts/validate_public_repository_surface.py` |
| Release status validation | `python scripts/validate_release_status.py --strict` |

