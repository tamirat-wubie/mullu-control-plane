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
| Runtime witness secret provisioner | `scripts/provision_runtime_witness_secret.py` binds `MULLU_RUNTIME_WITNESS_SECRET` into GitHub Actions without printing the secret | Reflected |
| Deployment target provisioner | `scripts/provision_deployment_target.py` binds `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` into GitHub repository variables | Reflected |
| Gateway ingress manifest | `k8s/mullu-gateway-ingress.yaml` publishes `/health` and `/gateway/witness` through the `mullu-gateway` service after host replacement | Reflected |
| Gateway ingress renderer | `scripts/render_gateway_ingress.py` renders a concrete ignored ingress manifest and optionally applies it through `kubectl` | Reflected |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` uploads `deployment-witness` artifact from the collector | Reflected |
| Gateway publication workflow | `.github/workflows/gateway-publication.yml` runs the self-gating publication orchestrator from GitHub with optional kubeconfig-backed ingress apply | Reflected |
| Deployment witness dispatcher | `scripts/dispatch_deployment_witness.py` verifies the runtime witness secret, dispatches the workflow, and downloads the artifact | Reflected |
| Deployment witness orchestrator | `scripts/orchestrate_deployment_witness.py` composes ingress render, target variable provisioning, optional preflight gating, and optional dispatch | Reflected |
| Deployment witness preflight | `scripts/preflight_deployment_witness.py` verifies DNS, GitHub variables, secret presence, workflow state, and endpoint contracts before dispatch | Reflected |
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
| Runtime witness secret provisioning | `python scripts/provision_runtime_witness_secret.py --runtime-env-output .change_assurance/runtime_witness_secret.env` |
| Deployment target provisioning | `python scripts/provision_deployment_target.py --gateway-url "$MULLU_GATEWAY_URL" --expected-environment pilot` |
| Gateway ingress validation | `python scripts/validate_gateway_ingress_manifest.py --allow-placeholder` |
| Gateway ingress rendering | `python scripts/render_gateway_ingress.py --gateway-host "$MULLU_GATEWAY_HOST"` |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` |
| Gateway publication workflow | `.github/workflows/gateway-publication.yml` |
| Deployment witness workflow dispatch | `python scripts/dispatch_deployment_witness.py` |
| Deployment witness orchestration | `python scripts/orchestrate_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --apply-ingress --require-preflight --dispatch` |
| Deployment witness preflight | `python scripts/preflight_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot` |
| Gateway runtime smoke probe | `python scripts/gateway_runtime_smoke.py` |

