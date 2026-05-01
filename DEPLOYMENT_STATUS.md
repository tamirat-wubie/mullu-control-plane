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
| Live deployment witness collector | `scripts/collect_deployment_witness.py` writes `.change_assurance/deployment_witness.json` from `/health`, `/gateway/witness`, and `/runtime/conformance` | Reflected |
| Runtime witness secret provisioner | `scripts/provision_runtime_witness_secret.py` binds `MULLU_RUNTIME_WITNESS_SECRET` into GitHub Actions without printing the secret | Reflected |
| Deployment target provisioner | `scripts/provision_deployment_target.py` binds `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` into GitHub repository variables | Reflected |
| Gateway ingress manifest | `k8s/mullu-gateway-ingress.yaml` publishes `/health` and `/gateway/witness` through the `mullu-gateway` service after host replacement | Reflected |
| Gateway ingress renderer | `scripts/render_gateway_ingress.py` renders a concrete ignored ingress manifest and optionally applies it through `kubectl` | Reflected |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` uploads `deployment-witness` artifact from the collector | Reflected |
| Gateway publication workflow | `.github/workflows/gateway-publication.yml` runs the self-gating publication orchestrator from GitHub with optional kubeconfig-backed ingress apply | Reflected |
| Gateway publication readiness report | `scripts/report_gateway_publication_readiness.py` derives the publication host, verifies GitHub/DNS readiness gates, and emits the exact dispatch command without exposing secret values | Reflected |
| Gateway publication readiness handoff | `scripts/dispatch_gateway_publication.py --readiness-report` consumes a ready publication report and re-validates dispatch prerequisites | Reflected |
| Gateway publication publisher | `scripts/publish_gateway_publication.py` writes readiness evidence, then optionally dispatches from that report through the handoff contract | Reflected |
| Gateway publication receipt | `.change_assurance/gateway_publication_receipt.json` records the publisher terminal local decision state and dispatch run metadata when present | Reflected |
| Gateway publication receipt validator | `scripts/validate_gateway_publication_receipt.py` validates receipt structure, readiness consistency, policy gates, and writes a validation report | Reflected |
| Gateway publication dispatcher | `scripts/dispatch_gateway_publication.py` verifies publication workflow prerequisites, dispatches `.github/workflows/gateway-publication.yml`, and downloads the witness artifact | Reflected |
| Deployment witness dispatcher | `scripts/dispatch_deployment_witness.py` verifies runtime witness and conformance secrets, dispatches the workflow, and downloads the artifact | Reflected |
| Deployment witness orchestrator | `scripts/orchestrate_deployment_witness.py` composes ingress render, target variable provisioning, MCP operator checklist validation, optional preflight gating, optional dispatch, and orchestration receipt output | Reflected |
| Deployment witness preflight | `scripts/preflight_deployment_witness.py` verifies DNS, GitHub variables, secret presence, workflow state, and endpoint contracts before dispatch | Reflected |
| MCP capability manifest validation | `scripts/validate_mcp_capability_manifest.py` validates certified MCP capability import, ownership, approval policy, and escalation policy records before startup | Reflected |
| MCP operator handoff checklist | `examples/mcp_operator_handoff_checklist.json` and `scripts/validate_mcp_operator_checklist.py` define release handoff gates for manifest validation, read-model inspection, execution evidence bundles, conformance collection, deployment preflight, and orchestration receipt closure | Reflected |
| Deployment orchestration receipt validator | `scripts/validate_deployment_orchestration_receipt.py` validates post-run orchestration receipts, including MCP checklist and preflight evidence gates | Reflected |
| MCP manifest runtime conformance | `/runtime/conformance` signs `mcp_capability_manifest_configured`, `mcp_capability_manifest_valid`, and `mcp_capability_manifest_capability_count` into deployment evidence | Reflected |
| MCP operator read model | `/mcp/operator/read-model` exposes MCP manifest state alongside capability, ownership, policy, escalation, and execution audit state | Reflected |
| Capability plan evidence bundles | `/capability-plans/{plan_id}/closure` exposes terminal plan certificates, evidence bundles, witnesses, and recovery attempts; `/runtime/conformance` gates on `capability_plan_bundle_canary_passed` | Reflected |
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
| Live deployment witness collection | `python scripts/collect_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" --conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET" --output .change_assurance/deployment_witness.json` |
| Runtime witness secret provisioning | `python scripts/provision_runtime_witness_secret.py --runtime-env-output .change_assurance/runtime_witness_secret.env` |
| Deployment target provisioning | `python scripts/provision_deployment_target.py --gateway-url "$MULLU_GATEWAY_URL" --expected-environment pilot` |
| Gateway ingress validation | `python scripts/validate_gateway_ingress_manifest.py --allow-placeholder` |
| Gateway ingress rendering | `python scripts/render_gateway_ingress.py --gateway-host "$MULLU_GATEWAY_HOST"` |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` |
| Gateway publication workflow | `.github/workflows/gateway-publication.yml` |
| Gateway publication readiness | `python scripts/report_gateway_publication_readiness.py --gateway-url "$MULLU_GATEWAY_URL" --dispatch-witness` |
| Gateway publication readiness handoff | `python scripts/dispatch_gateway_publication.py --readiness-report .change_assurance/gateway_publication_readiness.json` |
| Gateway publication publisher | `python scripts/publish_gateway_publication.py --gateway-url "$MULLU_GATEWAY_URL" --dispatch-witness --dispatch --receipt-output .change_assurance/gateway_publication_receipt.json` |
| Gateway publication receipt validation | `python scripts/validate_gateway_publication_receipt.py --receipt .change_assurance/gateway_publication_receipt.json --require-ready --require-dispatched --require-success` |
| Gateway publication dispatch | `python scripts/dispatch_gateway_publication.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --dispatch-witness` |
| Deployment witness workflow dispatch | `python scripts/dispatch_deployment_witness.py` |
| Deployment witness orchestration | `python scripts/orchestrate_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --apply-ingress --require-preflight --require-mcp-operator-checklist --dispatch --orchestration-output "$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT"` |
| Deployment witness orchestration receipt | `.change_assurance/deployment_witness_orchestration.json` |
| Deployment witness preflight | `python scripts/preflight_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot` |
| MCP operator handoff checklist | `python scripts/validate_mcp_operator_checklist.py --checklist examples/mcp_operator_handoff_checklist.json --json` |
| MCP capability manifest validation | `python scripts/validate_mcp_capability_manifest.py --manifest examples/mcp_capability_manifest.json --json` |
| MCP-aware deployment preflight | `python scripts/preflight_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --mcp-capability-manifest "$MULLU_MCP_CAPABILITY_MANIFEST_PATH"` |
| MCP operator read model | `curl -H "X-Mullu-Authority-Secret: $MULLU_AUTHORITY_OPERATOR_SECRET" "$MULLU_GATEWAY_URL/mcp/operator/read-model?audit_limit=25"` |
| MCP-gated deployment orchestration | `python scripts/orchestrate_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --require-mcp-operator-checklist --require-preflight --orchestration-output "$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT"` |
| Deployment orchestration receipt validation | `python scripts/validate_deployment_orchestration_receipt.py --receipt "$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT" --require-mcp-operator-checklist --require-preflight --expected-environment pilot` |
| Capability plan closure bundle | `curl -H "X-Mullu-Authority-Secret: $MULLU_AUTHORITY_OPERATOR_SECRET" "$MULLU_GATEWAY_URL/capability-plans/{plan_id}/closure"` |
| Gateway runtime smoke probe | `python scripts/gateway_runtime_smoke.py` |

