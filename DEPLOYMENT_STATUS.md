<!--
Purpose: Public deployment-health witness for GitHub-visible state.
Governance scope: runtime endpoint publication, health evidence, and closure
  obligations for production deployment reflection.
Dependencies: STATUS.md, GITHUB_SURFACE.md, DEPLOYMENT.md, RUNBOOK.md.
Invariants: Absence of live deployment evidence is explicit; no production health
  claim is made without named endpoint evidence.
-->

# Deployment Status Witness

**Last audited:** 2026-05-01
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
| Live deployment witness collector | `scripts/collect_deployment_witness.py` writes `.change_assurance/deployment_witness.json` from `/health`, `/gateway/witness`, and `/runtime/conformance`; publication requires both runtime and authority responsibility debt to be clear | Reflected |
| Production Evidence Plane | `/deployment/witness`, `/capabilities/evidence`, `/audit/verify`, and `/proof/verify` expose signed deployment posture, capability evidence, audit verification, and proof verification; `--require-production-evidence` makes them publication gates | Reflected |
| Production evidence endpoint schemas | `schemas/production_evidence_witness.schema.json`, `schemas/capability_evidence_endpoint.schema.json`, `schemas/audit_verification_endpoint.schema.json`, and `schemas/proof_verification_endpoint.schema.json` define the live endpoint contracts | Reflected |
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
| Adapter worker dependency packaging | `mcoi/pyproject.toml`, `Dockerfile`, and `docker-compose.yml` package browser, document, voice, and email/calendar worker dependencies behind optional dependency groups and the `adapter-workers` compose profile | Reflected |
| Adapter worker signed dispatch clients | `gateway/adapter_worker_clients.py` and `gateway/capability_dispatch.py` route browser, document, voice, and email/calendar capabilities through signed worker requests with response-signature and receipt validation | Reflected |
| Communication capability capsule | `capsules/communication.json` and `capabilities/communication/capability_pack.json` expose governed `email.*` and `calendar.*` records for signed email/calendar worker dispatch | Reflected |
| Email/calendar connector adapter | `gateway/email_calendar_connector_adapters.py` binds Gmail, Google Calendar, and Microsoft Graph HTTP operations to the signed email/calendar worker while failing closed without connector credentials or approval evidence | Reflected |
| Capability adapter live receipt producer | `scripts/produce_capability_adapter_live_receipts.py` writes browser, document, voice, and email/calendar live receipt artifacts while failing closed when sandbox evidence, parser dependencies, provider credentials, live audio input, or communication worker proof are missing | Reflected |
| Capability adapter evidence collector | `scripts/collect_capability_adapter_evidence.py` writes `.change_assurance/capability_adapter_evidence.json` from browser, document, voice, and email/calendar dependency checks plus live adapter receipts | Reflected |
| Capability adapter closure planner | `scripts/plan_capability_adapter_closure.py` converts adapter evidence blockers into dependency, credential, and live-receipt actions without claiming closure | Reflected |
| Capability adapter closure plan schema validator | `scripts/validate_capability_adapter_closure_plan_schema.py` validates adapter closure plan shape, action counts, proof contracts, and blocker coverage before aggregate promotion planning | Reflected |
| Deployment publication closure planner | `scripts/plan_deployment_publication_closure.py` converts deployment witness, responsibility-debt, and public-health blockers into approval-bound publication actions without mutating status | Reflected |
| General-agent promotion closure planner | `scripts/plan_general_agent_promotion_closure.py` aggregates adapter and deployment closure plans into one operator-facing promotion plan | Reflected |
| General-agent promotion closure plan schema | `schemas/general_agent_promotion_closure_plan.schema.json` defines the public operator-facing promotion closure plan contract | Reflected |
| General-agent promotion closure plan schema validator | `scripts/validate_general_agent_promotion_closure_plan_schema.py` validates aggregate closure plan shape and semantic action counts before approval or execution | Reflected |
| General-agent promotion closure plan validator | `scripts/validate_general_agent_promotion_closure_plan.py` verifies aggregate promotion actions match source adapter and deployment plans before use | Reflected |
| General-agent promotion handoff packet | `docs/59_general_agent_promotion_handoff_packet.md` is the single operator entry point for the checklist, runbook, closure plans, validation reports, blockers, and terminal proof command | Reflected |
| General-agent promotion machine handoff packet | `examples/general_agent_promotion_handoff_packet.json` is the schema-backed machine-readable handoff packet for operator execution | Reflected |
| General-agent promotion environment bindings | `examples/general_agent_promotion_environment_bindings.json` and `scripts/validate_general_agent_promotion_environment_bindings.py` define the presence-only operator environment binding contract without serializing secret values | Reflected |
| General-agent promotion environment binding receipt | `scripts/emit_general_agent_promotion_environment_binding_receipt.py` writes `.change_assurance/general_agent_promotion_environment_binding_receipt.json`; `scripts/validate_general_agent_promotion_environment_binding_receipt.py` verifies binding presence, derived readiness, and no serialized secret values | Reflected |
| General-agent promotion handoff packet validator | `scripts/validate_general_agent_promotion_handoff_packet.py` validates the machine handoff packet, blockers, entry points, and terminal proof command | Reflected |
| General-agent promotion handoff preflight | `scripts/preflight_general_agent_promotion_handoff.py` verifies packet, checklist, closure reports, readiness report, and environment binding presence without printing secret values | Reflected |
| Deployment capability capsule | `capsules/deployment.json` and `capabilities/deployment/capability_pack.json` govern `deployment.witness.collect` and `deployment.witness.publish.with_approval` | Reflected |
| General-agent promotion validator | `scripts/validate_general_agent_promotion.py --strict` blocks production general-agent claims until governed capability records, real browser/document/voice adapters, sandbox runner evidence, MCP import governance, deployment witness publication, and public health evidence all pass | Reflected |
| Governed runtime promotion validator | `scripts/validate_governed_runtime_promotion.py --strict` provides the domain-neutral terminal validator while preserving the existing promotion readiness evidence contract | Reflected |
| Public production health | No governed production endpoint is declared in this repository | Not reflected |
| Deployment badge | No GitHub-visible deployment badge is declared | Not reflected |

## GitHub Runtime Input State

| Input surface | Observed state |
|---|---|
| Runtime witness secret | GitHub Actions secret name `MULLU_RUNTIME_WITNESS_SECRET` is present; secret value is not printed |
| Runtime conformance secret | GitHub Actions secret name `MULLU_RUNTIME_CONFORMANCE_SECRET` is present; secret value is not printed |
| Deployment witness secret | GitHub Actions secret name `MULLU_DEPLOYMENT_WITNESS_SECRET` is present; secret value is not printed |
| Deployment target variables | GitHub repository variables `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` are not currently set |
| Deployment witness workflow runs | No `deployment-witness.yml` workflow runs are currently recorded |

## Closure Requirements

Before this witness can claim public deployment health, the repository must name:

1. Production API base URL.
2. Production gateway base URL.
3. Health endpoint response contract.
4. Last successful health-check timestamp.
5. Operator or automation identity that produced the health witness.
6. Failure handling path for stale or unavailable health evidence.
7. Capability worker endpoint and last successful signed worker-response check.
8. Runtime witness evidence with `responsibility_debt_clear=true`.
9. Deployment witness evidence with `runtime_responsibility_debt_clear=true` and `authority_responsibility_debt_clear=true`.
10. Production Evidence Plane evidence from `/deployment/witness`, `/capabilities/evidence`, `/audit/verify`, and `/proof/verify`.

## Proof Chain

| Check | Command |
|---|---|
| Public surface validation | `python scripts/validate_public_repository_surface.py` |
| Release status validation | `python scripts/validate_release_status.py --strict` |
| Gateway deployment validation | `python scripts/validate_gateway_deployment_env.py --strict` |
| Local pilot proof slice | `python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json` |
| Live deployment witness collection | `python scripts/collect_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" --conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET" --output .change_assurance/deployment_witness.json` |
| Live production evidence collection | `python scripts/collect_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" --conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET" --deployment-witness-secret "$MULLU_DEPLOYMENT_WITNESS_SECRET" --require-production-evidence --output .change_assurance/deployment_witness.json` |
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
| Deployment publication closure | `python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json` |
| Deployment publication closure validation | `.change_assurance/deployment_publication_closure_validation.json` |
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
| Adapter worker signed dispatch test | `python -m pytest tests/test_gateway/test_adapter_worker_clients.py tests/test_gateway/test_adapter_worker_dispatch.py` |
| Browser sandbox evidence production | `python scripts/produce_browser_sandbox_evidence.py --output "$MULLU_BROWSER_SANDBOX_EVIDENCE" --strict` |
| Sandbox execution receipt validation | `python scripts/validate_sandbox_execution_receipt.py --receipt "$MULLU_BROWSER_SANDBOX_EVIDENCE" --capability-prefix browser. --require-no-workspace-changes --json` |
| Browser sandbox evidence validation | `python scripts/validate_browser_sandbox_evidence.py --evidence "$MULLU_BROWSER_SANDBOX_EVIDENCE" --json` |
| Capability adapter live receipt production | `python scripts/produce_capability_adapter_live_receipts.py --strict --browser-sandbox-evidence "$MULLU_BROWSER_SANDBOX_EVIDENCE" --voice-audio-path "$MULLU_VOICE_PROBE_AUDIO"` |
| Capability adapter evidence collection | `python scripts/collect_capability_adapter_evidence.py --strict` |
| Capability adapter closure planning | `python scripts/plan_capability_adapter_closure.py --json` |
| Capability adapter closure plan schema validation | `python scripts/validate_capability_adapter_closure_plan_schema.py --strict` |
| Deployment publication closure planning | `python scripts/plan_deployment_publication_closure.py --json` |
| General-agent promotion closure planning | `python scripts/plan_general_agent_promotion_closure.py --json` |
| General-agent promotion closure plan schema validation | `python scripts/validate_general_agent_promotion_closure_plan_schema.py --strict` |
| General-agent promotion closure plan validation | `python scripts/validate_general_agent_promotion_closure_plan.py --strict` |
| General-agent promotion operator checklist validation | `python scripts/validate_general_agent_promotion_operator_checklist.py --checklist examples/general_agent_promotion_operator_checklist.json --json` |
| General-agent promotion environment binding validation | `python scripts/validate_general_agent_promotion_environment_bindings.py --contract examples/general_agent_promotion_environment_bindings.json --json` |
| General-agent promotion environment binding receipt | `python scripts/emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance/general_agent_promotion_environment_binding_receipt.json --json` |
| General-agent promotion environment binding receipt validation | `python scripts/validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance/general_agent_promotion_environment_binding_receipt.json --require-ready --json` |
| General-agent promotion handoff packet | `docs/59_general_agent_promotion_handoff_packet.md` |
| General-agent promotion machine handoff packet validation | `python scripts/validate_general_agent_promotion_handoff_packet.py --packet examples/general_agent_promotion_handoff_packet.json --json` |
| General-agent promotion handoff preflight | `python scripts/preflight_general_agent_promotion_handoff.py --output .change_assurance/general_agent_promotion_handoff_preflight.json --strict --json` |
| General-agent promotion handoff preflight validation | `python scripts/validate_general_agent_promotion_handoff_preflight.py --report .change_assurance/general_agent_promotion_handoff_preflight.json --require-ready --json` |
| General-agent promotion validation | `python scripts/validate_general_agent_promotion.py --strict` |
| Governed runtime promotion validation | `python scripts/validate_governed_runtime_promotion.py --strict` |

