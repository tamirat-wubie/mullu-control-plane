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
**Gateway health endpoint:** `/health`
**Gateway runtime witness endpoint:** `/gateway/witness`
**Restricted capability worker health endpoint:** `/health`
**API health endpoint:** `not-declared`

## Reflection Summary

| Surface | Witness | Status |
|---|---|---|
| Local API health contract | `RUNBOOK.md` and `DEPLOYMENT.md` document `/health` checks | Reflected |
| Local gateway health contract | `README.md` documents `http://localhost:8001/health` | Reflected |
| Local gateway runtime witness | `DEPLOYMENT.md` documents `/gateway/witness` and `/runtime/witness` | Reflected |
| Restricted capability worker | `DEPLOYMENT.md`, `docker-compose.yml`, and `k8s/mullu-api.yaml` declare `gateway.capability_worker:app` | Reflected |
| Local pilot proof slice | `scripts/pilot_proof_slice.py` emits `.change_assurance/pilot_proof_slice_witness.json` through gateway closure | Reflected |
| Live deployment witness collector | `scripts/collect_deployment_witness.py` writes `.change_assurance/deployment_witness.json` from `/health` and `/gateway/witness` | Reflected |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` uploads `deployment-witness` artifact from the collector | Reflected |
| Deployment witness dispatcher | `scripts/dispatch_deployment_witness.py` verifies the runtime witness secret, dispatches the workflow, and downloads the artifact | Reflected |
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
7. Capability worker endpoint and last successful signed worker-response check.

## Proof Chain

| Check | Command |
|---|---|
| Public surface validation | `python scripts/validate_public_repository_surface.py` |
| Release status validation | `python scripts/validate_release_status.py --strict` |
| Gateway deployment validation | `python scripts/validate_gateway_deployment_env.py --strict` |
| Local pilot proof slice | `python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json` |
| Live deployment witness collection | `python scripts/collect_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" --output .change_assurance/deployment_witness.json` |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` |
| Deployment witness workflow dispatch | `python scripts/dispatch_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --expected-environment pilot` |
| Gateway runtime smoke probe | `python scripts/gateway_runtime_smoke.py` |

