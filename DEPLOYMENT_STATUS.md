<!--
Purpose: Public deployment-health witness for GitHub-visible state.
Governance scope: runtime endpoint publication, health evidence, and closure
  obligations for production deployment reflection.
Dependencies: STATUS.md, GITHUB_SURFACE.md, DEPLOYMENT.md, RUNBOOK.md.
Invariants: Live deployment evidence is named; no production health claim is made
  without matching endpoint evidence.
-->

# Deployment Status Witness

**Last audited:** 2026-06-14
**Deployment witness state:** `published`
**Public production health endpoint:** `https://api.mullusi.com/health`
**Gateway health endpoint:** `/health`
**Gateway runtime witness endpoint:** `/gateway/witness`
**Restricted capability worker health endpoint:** `/health`
**API health endpoint:** `https://api.mullusi.com/health`

## Reflection Summary

| Surface | Witness | Status |
|---|---|---|
| Local API health contract | `RUNBOOK.md` and `DEPLOYMENT.md` document `/health` checks | Reflected |
| Local gateway health contract | `README.md` documents `http://localhost:8001/health` | Reflected |
| README production claim boundary | `DEPLOYMENT_STATUS.md` now records the published public-health declaration; README and status-summary surfaces must stay synchronized with this witness | Reflected |
| Local gateway runtime witness | `DEPLOYMENT.md` documents `/gateway/witness` and `/runtime/witness` | Reflected |
| Restricted capability worker | `DEPLOYMENT.md`, `docker-compose.yml`, and `k8s/mullu-api.yaml` declare `gateway.capability_worker:app` | Reflected |
| Local pilot proof slice | `scripts/pilot_proof_slice.py` emits `.change_assurance/pilot_proof_slice_witness.json` through gateway closure | Reflected |
| Runtime conformance collector | `scripts/collect_runtime_conformance.py` writes `.change_assurance/runtime_conformance_certificate.json` from `/runtime/conformance` with signature, authority read-model, and schema-envelope checks | Reflected |
| Runtime conformance collection schema | `schemas/runtime_conformance_collection.schema.json` defines the persisted collector envelope for live conformance probes | Reflected |
| Live deployment witness collector | `scripts/collect_deployment_witness.py` writes `.change_assurance/deployment_witness.json` from `/health`, `/gateway/witness`, and `/runtime/conformance`; publication requires both runtime and authority responsibility debt to be clear | Reflected |
| Production Evidence Plane | `/deployment/witness`, `/capabilities/evidence`, `/audit/verify`, and `/proof/verify` expose signed deployment posture, capability evidence, audit verification, and proof verification; `--require-production-evidence` makes them publication gates | Reflected |
| Production evidence endpoint schemas | `schemas/production_evidence_witness.schema.json`, `schemas/capability_evidence_endpoint.schema.json`, `schemas/audit_verification_endpoint.schema.json`, and `schemas/proof_verification_endpoint.schema.json` define the live endpoint contracts | Reflected |
| Runtime witness secret provisioner | `scripts/provision_runtime_witness_secret.py` binds `MULLU_RUNTIME_WITNESS_SECRET` into GitHub Actions without printing the secret | Reflected |
| Deployment target provisioner | `scripts/provision_deployment_target.py` binds `MULLU_GATEWAY_URL` and `MULLU_EXPECTED_RUNTIME_ENV` into GitHub repository variables | Reflected |
| Gateway ingress manifest | `k8s/mullu-gateway-ingress.yaml` publishes `/health`, `/gateway/witness`, and `/runtime/conformance` through the `mullu-gateway` service after host replacement | Reflected |
| Gateway ingress renderer | `scripts/render_gateway_ingress.py` renders a concrete ignored ingress manifest and optionally applies it through `kubectl` | Reflected |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` uploads `runtime-conformance-collection` and `deployment-witness` artifacts from the collectors and conditionally emits a public-health declaration receipt when `operator_approval_ref` is supplied | Reflected |
| Gateway publication workflow | `.github/workflows/gateway-publication.yml` runs the self-gating publication orchestrator from GitHub with optional kubeconfig-backed ingress apply | Reflected |
| API image publication workflow | `.github/workflows/api-image-publication.yml` builds the root `Dockerfile`, publishes to GHCR only when `confirm_publication=true` and `operator_approval_ref` is supplied, and uploads `.change_assurance/api_image_publication_receipt.json` without secret values, DNS mutation, or runtime mutation | Reflected |
| Gateway publication readiness report | `scripts/report_gateway_publication_readiness.py` derives the publication host, verifies GitHub/DNS readiness gates, and emits the exact dispatch command without exposing secret values | Reflected |
| Gateway publication readiness handoff | `scripts/dispatch_gateway_publication.py --readiness-report` consumes a ready publication report and re-validates dispatch prerequisites | Reflected |
| Gateway publication publisher | `scripts/publish_gateway_publication.py` writes readiness evidence, then optionally dispatches from that report through the handoff contract | Reflected |
| Gateway publication receipt | `.change_assurance/gateway_publication_receipt.json` records the publisher terminal local decision state and dispatch run metadata when present | Reflected |
| Gateway publication receipt validator | `scripts/validate_gateway_publication_receipt.py` validates receipt structure, readiness consistency, policy gates, and writes a validation report | Reflected |
| Deployment publication evidence packet collector | `scripts/collect_deployment_publication_evidence_packet.py` aggregates upstream API readiness, upstream blocker, DNS target binding, DNS resolution, closure plan, and dispatch dry-run evidence before publication | Reflected |
| Deployment publication evidence packet validator | `scripts/validate_deployment_publication_evidence_packet.py --require-ready` blocks publication while the aggregate packet is valid but not ready | Reflected |
| Deployment publication operator input request | `scripts/emit_deployment_publication_operator_input_request.py` converts blocked packet evidence into public-safe missing input names and blocked publication actions | Reflected |
| Deployment publication operator input request validator | `scripts/validate_deployment_publication_operator_input_request.py` proves the missing-input request is schema-valid and publication allowance remains consistent with readiness | Reflected |
| Deployment upstream blocker receipt | `scripts/emit_deployment_upstream_blocker_receipt.py` records upstream API/DNS readiness blockers before DNS publication | Reflected |
| Deployment upstream blocker validator | `scripts/validate_deployment_upstream_blocker_receipt.py --require-ready` blocks DNS publication while upstream API provisioning or DNS publication is not allowed | Reflected |
| Upstream API production readiness reporter | `mullusi-site/scripts/check-api-production-readiness.mjs --require-ready` aggregates recovery, runtime host, managed PostgreSQL, schema, secret store, preflight, persistence, firewall, TLS, rollback, private runtime witness, and DNS authority evidence before `api.mullusi.com` DNS publication | Reflected |
| Gateway DNS target binding receipt | `scripts/emit_gateway_dns_target_binding_receipt.py` records the selected gateway host, URL, environment, DNS record type, target, and provider before DNS publication | Reflected |
| Gateway DNS target binding validator | `scripts/validate_gateway_dns_target_binding_receipt.py --require-ready` blocks DNS publication when the origin target, record type, or provider is missing or structurally invalid | Reflected |
| Gateway publication dispatcher | `scripts/dispatch_gateway_publication.py` verifies publication workflow prerequisites, including runtime witness, conformance, deployment witness, and apply-ingress kubeconfig secret gates, dispatches `.github/workflows/gateway-publication.yml`, and downloads the witness artifact | Reflected |
| Deployment witness dispatcher | `scripts/dispatch_deployment_witness.py` verifies runtime witness, conformance, and deployment witness secrets, dispatches the workflow, and downloads the artifact | Reflected |
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
| Deployment publication closure plan schema validator | `scripts/validate_deployment_publication_closure_plan_schema.py` validates deployment publication closure plan shape, action counts, approval requirements, and blocker coverage before aggregate promotion planning | Reflected |
| Public health declaration applier | `scripts/apply_deployment_publication_status.py` updates this status witness only after a schema-valid published deployment witness, matching HTTPS health endpoint, and operator approval reference are present | Reflected |
| Public health declaration schema | `schemas/public_production_health_declaration.schema.json` defines the receipt emitted by the public health declaration applier | Reflected |
| General-agent promotion closure planner | `scripts/plan_general_agent_promotion_closure.py` aggregates adapter and deployment closure plans into one operator-facing promotion plan | Reflected |
| General-agent promotion closure plan schema | `schemas/general_agent_promotion_closure_plan.schema.json` defines the public operator-facing promotion closure plan contract | Reflected |
| General-agent promotion closure plan schema validator | `scripts/validate_general_agent_promotion_closure_plan_schema.py` validates aggregate closure plan shape and semantic action counts before approval or execution | Reflected |
| General-agent promotion closure plan validator | `scripts/validate_general_agent_promotion_closure_plan.py` verifies aggregate promotion actions match source adapter and deployment plans before use | Reflected |
| General-agent promotion handoff packet | `docs/59_general_agent_promotion_handoff_packet.md` is the single operator entry point for the checklist, runbook, closure plans, validation reports, blockers, and terminal proof command | Reflected |
| General-agent promotion machine handoff packet | `examples/general_agent_promotion_handoff_packet.json` is the schema-backed machine-readable handoff packet for operator execution | Reflected |
| General-agent promotion environment bindings | `examples/general_agent_promotion_environment_bindings.json` and `scripts/validate_general_agent_promotion_environment_bindings.py` define the presence-only operator environment binding contract for adapter evidence, gateway publication, runtime witness, conformance, deployment witness, and authority secrets without serializing values | Reflected |
| General-agent promotion environment binding receipt | `scripts/emit_general_agent_promotion_environment_binding_receipt.py` writes `.change_assurance/general_agent_promotion_environment_binding_receipt.json`; `scripts/validate_general_agent_promotion_environment_binding_receipt.py` verifies binding presence, derived readiness, and no serialized secret values | Reflected |
| General-agent promotion handoff packet validator | `scripts/validate_general_agent_promotion_handoff_packet.py` validates the machine handoff packet, blockers, entry points, and terminal proof command | Reflected |
| General-agent promotion handoff preflight | `scripts/preflight_general_agent_promotion_handoff.py` verifies packet, checklist, closure reports, readiness report, and environment binding presence without printing secret values | Reflected |
| Deployment capability capsule | `capsules/deployment.json` and `capabilities/deployment/capability_pack.json` govern `deployment.witness.collect` and `deployment.witness.publish.with_approval` | Reflected |
| General-agent promotion validator | `scripts/validate_general_agent_promotion.py --strict` blocks production general-agent claims until governed capability records, real browser/document/voice adapters, sandbox runner evidence, MCP import governance, deployment witness publication, and public health evidence all pass | Reflected |
| Governed runtime promotion validator | `scripts/validate_governed_runtime_promotion.py --strict` provides the domain-neutral terminal validator while preserving the existing promotion readiness evidence contract | Reflected |
| Governed swarm extension-health pilot gate | `scripts/collect_governed_swarm_staging_activation_witness.py` now probes `/api/v1/health/extensions`; staging evidence bundles and pilot promotion readiness require the governed swarm extension to be registered, enabled, mounted, and audit-store-configured without exposing raw filesystem paths | Reflected |
| Public production health | Declared from a verified published deployment witness; `https://api.mullusi.com/health` is the public health endpoint, `.change_assurance/deployment_witness.json` records `deployment_claim=published`, and `.change_assurance/public_production_health_declaration.json` records the operator-approved declaration receipt | Reflected |
| Govern Cloud public route monitor | `scripts/collect_govern_cloud_public_route_monitor.py` writes `.change_assurance/govern_cloud_public_route_monitor_receipt.json` from `GET /v1/health`, `GET /v1/version`, and the blocked `POST /v1/govern/evaluate` guard; `docs/GOVERN_CLOUD_PUBLIC_ROUTE_MONITOR_RUNBOOK.md` defines cadence and rollback | Reflected |
| Govern Cloud evaluate-route rollback witness | `scripts/validate_govern_evaluate_route_rollback.py` verifies `/v1/health` and `/v1/version` remain public read routes while `POST /v1/govern/evaluate` returns 404 without outbound proxy transport | Reflected |
| Personal assistant public console probe | `scripts/collect_personal_assistant_public_console_probe.py` writes `examples/personal_assistant_public_console_probe_receipt.json` from the public read-only JSON and HTML console routes while preserving no-effect authority boundaries | Reflected |
| Personal assistant component witness | `scripts/collect_personal_assistant_component_witness.py` writes `examples/personal_assistant_component_witness_receipt.json` from local component graph, bundle compilation, and lifecycle receipts while preserving draft-only/no-effect authority boundaries | Reflected |
| Personal assistant foundation evidence | `scripts/collect_personal_assistant_foundation_evidence.py` writes `examples/personal_assistant_foundation_evidence_receipt.json` from the console read model, public console probe, and component witness while preserving no-effect foundation boundaries | Reflected |
| Personal assistant readiness index | `scripts/collect_personal_assistant_readiness_index.py` writes `examples/personal_assistant_readiness_index_receipt.json` from the foundation evidence receipt, console read model, skill registry, and capability pack while preserving live-execution and customer-readiness blocks | Reflected |
| Personal assistant coherence ledger | `scripts/collect_personal_assistant_coherence_ledger.py` writes `examples/personal_assistant_coherence_ledger_receipt.json` from the readiness index, console read model, skill registry, and capability pack while preserving no-effect dependency and authority-block records | Reflected |
| Personal assistant authority coverage | `scripts/collect_personal_assistant_authority_coverage.py` writes `examples/personal_assistant_authority_coverage_receipt.json` from the skill registry, approval matrix, skill policy, capability pack, and coherence ledger while preserving no-effect execution authority boundaries | Reflected |
| Personal assistant capsule alignment | `scripts/collect_personal_assistant_capsule_alignment.py` writes `examples/personal_assistant_capsule_alignment_receipt.json` from the capsule, capability pack, protocol manifest, and authority coverage receipt while preserving no-effect capsule and schema binding boundaries | Reflected |
| Personal assistant policy matrix | `scripts/collect_personal_assistant_policy_matrix.py` writes `examples/personal_assistant_policy_matrix_receipt.json` from the skill policy, approval matrix, capsule, authority coverage, and capsule alignment receipts while preserving no-effect approval and payload-redaction boundaries | Reflected |
| Personal assistant runtime boundary | `scripts/collect_personal_assistant_runtime_boundary.py` writes `examples/personal_assistant_runtime_boundary_receipt.json` from runtime module source, capability pack, and policy matrix evidence while preserving no-effect connector, deployment, memory, and system-of-record boundaries | Reflected |
| Personal assistant foundation closure packet | `scripts/collect_personal_assistant_foundation_closure_packet.py` writes `examples/personal_assistant_foundation_closure_packet.json` from the checked-in foundation receipt chain while preserving no-effect live connector, memory, deployment, customer-readiness, Nested Mind, and terminal-closure boundaries | Reflected |
| Deployment badge | No GitHub-visible deployment badge is declared | Not reflected |

## GitHub Runtime Input State

| Input surface | Observed state |
|---|---|
| Runtime witness secret | GitHub Actions secret name `MULLU_RUNTIME_WITNESS_SECRET` is present; secret value is not printed |
| Runtime conformance secret | GitHub Actions secret name `MULLU_RUNTIME_CONFORMANCE_SECRET` is present; secret value is not printed |
| Deployment witness secret | GitHub Actions secret name `MULLU_DEPLOYMENT_WITNESS_SECRET` is present; secret value is not printed |
| Authority operator secret | GitHub Actions secret name `MULLU_AUTHORITY_OPERATOR_SECRET` is present; secret value is not printed |
| Deployment target variables | GitHub repository variables `MULLU_GATEWAY_URL=https://api.mullusi.com` and `MULLU_EXPECTED_RUNTIME_ENV=pilot` are set |
| Observed pilot health probe URL | `https://api.mullusi.com/health` is the declared public production health endpoint backed by the published deployment witness and public-health declaration receipt |
| Upstream API readiness | `api.mullusi.com` has a verified published deployment witness, clear runtime and authority responsibility debt, production evidence closure, and declared public health endpoint `https://api.mullusi.com/health` |
| Deployment witness workflow runs | A deployment witness workflow run collected the published witness for `https://api.mullusi.com`; the local deployment witness records verified signatures, clear runtime and authority responsibility debt, production evidence closure, and `deployment_claim=published` |
| Gateway publication workflow runs | `gateway-publication.yml` run `27489039439` completed successfully and dispatched deployment witness run `27489044697` |
| API image publication workflow runs | `.github/workflows/api-image-publication.yml` is the approval-bound GHCR publication lane for immutable API image digest evidence; use the uploaded `api-image-publication-receipt` artifact as the public-safe production image evidence reference |

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
10. Runtime conformance collection evidence from `.change_assurance/runtime_conformance_certificate.json`.
11. Production Evidence Plane evidence from `/deployment/witness`, `/capabilities/evidence`, `/audit/verify`, and `/proof/verify`.

## Proof Chain

| Check | Command |
|---|---|
| Public surface validation | `python scripts/validate_public_repository_surface.py` |
| Release status validation | `python scripts/validate_release_status.py --strict` |
| Gateway deployment validation | `python scripts/validate_gateway_deployment_env.py --strict` |
| Local pilot proof slice | `python scripts/pilot_proof_slice.py --output .change_assurance/pilot_proof_slice_witness.json` |
| Runtime conformance collection | `python scripts/collect_runtime_conformance.py --gateway-url "$MULLU_GATEWAY_URL" --conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET" --authority-operator-secret "$MULLU_AUTHORITY_OPERATOR_SECRET" --output .change_assurance/runtime_conformance_certificate.json` |
| Runtime conformance collection schema | `schemas/runtime_conformance_collection.schema.json` |
| Live deployment witness collection | `python scripts/collect_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" --conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET" --output .change_assurance/deployment_witness.json` |
| Live production evidence collection | `python scripts/collect_deployment_witness.py --gateway-url "$MULLU_GATEWAY_URL" --witness-secret "$MULLU_RUNTIME_WITNESS_SECRET" --conformance-secret "$MULLU_RUNTIME_CONFORMANCE_SECRET" --deployment-witness-secret "$MULLU_DEPLOYMENT_WITNESS_SECRET" --require-production-evidence --output .change_assurance/deployment_witness.json` |
| Runtime witness secret provisioning | `python scripts/provision_runtime_witness_secret.py --runtime-env-output .change_assurance/runtime_witness_secret.env` |
| Deployment target provisioning | `python scripts/provision_deployment_target.py --gateway-url "$MULLU_GATEWAY_URL" --expected-environment pilot` |
| Gateway ingress validation | `python scripts/validate_gateway_ingress_manifest.py --allow-placeholder` |
| Gateway ingress rendering | `python scripts/render_gateway_ingress.py --gateway-host "$MULLU_GATEWAY_HOST"` |
| Manual deployment witness workflow | `.github/workflows/deployment-witness.yml` |
| Gateway publication workflow | `.github/workflows/gateway-publication.yml` |
| API image publication workflow validation | `python scripts/validate_api_image_publication_workflow.py` |
| API image publication workflow | `.github/workflows/api-image-publication.yml` |
| Gateway publication readiness | `python scripts/report_gateway_publication_readiness.py --gateway-url "$MULLU_GATEWAY_URL" --dispatch-witness` |
| Gateway publication readiness handoff | `python scripts/dispatch_gateway_publication.py --readiness-report .change_assurance/gateway_publication_readiness.json` |
| Upstream API production readiness reporter | `(from mullusi-site) node scripts/check-api-production-readiness.mjs --require-ready --production-image-published --runtime-host-ready --managed-postgres-ready --schema-applied --production-secrets-stored --deploy-env-ready --release-preflight-ready --persistence-ready --host-firewall-configured --tls-certificate-ready --rollback-path-defined --private-runtime-witness-ready --dns-authority-ready` |
| Deployment publication evidence packet collection | `python scripts/collect_deployment_publication_evidence_packet.py --output-dir .change_assurance\deployment_publication_evidence_packet --gateway-url "$env:MULLU_GATEWAY_URL" --expected-environment "$env:MULLU_EXPECTED_RUNTIME_ENV" --upstream-readiness-report "$env:UPSTREAM_API_READINESS_REPORT" --dns-record-type "$env:MULLU_GATEWAY_DNS_RECORD_TYPE" --dns-target "$env:MULLU_GATEWAY_DNS_TARGET" --dns-provider "$env:MULLU_DNS_PROVIDER" --dispatch-witness --json` |
| Deployment publication evidence packet validation | `python scripts/validate_deployment_publication_evidence_packet.py --packet .change_assurance\deployment_publication_evidence_packet\deployment_publication_evidence_packet.json --output .change_assurance\deployment_publication_evidence_packet\deployment_publication_evidence_packet_validation.json --require-ready --json` |
| Deployment publication operator input request | `python scripts/emit_deployment_publication_operator_input_request.py --packet .change_assurance\deployment_publication_evidence_packet\deployment_publication_evidence_packet.json --output .change_assurance\deployment_publication_evidence_packet\deployment_publication_operator_input_request.json --json` |
| Deployment publication operator input request validation | `python scripts\validate_deployment_publication_operator_input_request.py --request .change_assurance\deployment_publication_evidence_packet\deployment_publication_operator_input_request.json --output .change_assurance\deployment_publication_evidence_packet\deployment_publication_operator_input_request_validation.json --json` |
| Deployment upstream blocker receipt | `python scripts/emit_deployment_upstream_blocker_receipt.py --target-gateway-url "$env:MULLU_GATEWAY_URL" --upstream-readiness-report "$env:UPSTREAM_API_READINESS_REPORT" --output .change_assurance\deployment_upstream_blocker_receipt.json --json` |
| Deployment upstream blocker validation | `python scripts/validate_deployment_upstream_blocker_receipt.py --receipt .change_assurance/deployment_upstream_blocker_receipt.json --output .change_assurance/deployment_upstream_blocker_receipt_validation.json --require-ready` |
| Gateway DNS target binding receipt | `python scripts/emit_gateway_dns_target_binding_receipt.py --gateway-host "$MULLU_GATEWAY_HOST" --gateway-url "$MULLU_GATEWAY_URL" --expected-environment "$MULLU_EXPECTED_RUNTIME_ENV" --record-type "$MULLU_GATEWAY_DNS_RECORD_TYPE" --target "$MULLU_GATEWAY_DNS_TARGET" --provider "$MULLU_DNS_PROVIDER" --output .change_assurance/gateway_dns_target_binding_receipt.json --json` |
| Gateway DNS target binding validation | `python scripts/validate_gateway_dns_target_binding_receipt.py --receipt .change_assurance/gateway_dns_target_binding_receipt.json --output .change_assurance/gateway_dns_target_binding_receipt_validation.json --require-ready` |
| Gateway DNS resolution receipt | `python scripts/collect_gateway_dns_resolution_receipt.py --gateway-url "$MULLU_GATEWAY_URL" --output .change_assurance/gateway_dns_resolution_receipt.json --json` |
| Gateway DNS resolution validation | `python scripts/validate_gateway_dns_resolution_receipt.py --receipt .change_assurance/gateway_dns_resolution_receipt.json --output .change_assurance/gateway_dns_resolution_receipt_validation.json --require-resolved` |
| Gateway publication publisher | `python scripts/publish_gateway_publication.py --gateway-url "$MULLU_GATEWAY_URL" --dispatch-witness --dispatch --receipt-output .change_assurance/gateway_publication_receipt.json` |
| Gateway publication receipt validation | `python scripts/validate_gateway_publication_receipt.py --receipt .change_assurance/gateway_publication_receipt.json --require-ready --require-dispatched --require-success` |
| Gateway publication dispatch | `python scripts/dispatch_gateway_publication.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --dispatch-witness` |
| Deployment witness workflow dispatch | `python scripts/dispatch_deployment_witness.py` |
| Deployment publication closure | `python scripts/validate_deployment_publication_closure.py --output .change_assurance/deployment_publication_closure_validation.json` |
| Deployment publication closure validation | `.change_assurance/deployment_publication_closure_validation.json` |
| Public health declaration application | `python scripts/apply_deployment_publication_status.py --operator-approval-ref "$MULLU_DEPLOYMENT_PUBLICATION_APPROVAL_REF" --receipt-output .change_assurance/public_production_health_declaration.json` |
| Public health declaration schema | `schemas/public_production_health_declaration.schema.json` |
| Deployment witness orchestration | `python scripts/orchestrate_deployment_witness.py --gateway-host "$MULLU_GATEWAY_HOST" --expected-environment pilot --apply-ingress --require-preflight --require-mcp-operator-checklist --skip-target-provisioning --dispatch --orchestration-output "$MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT"` |
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
| Deployment publication closure plan schema validation | `python scripts/validate_deployment_publication_closure_plan_schema.py --strict` |
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
| Personal assistant public console probe | `python scripts/collect_personal_assistant_public_console_probe.py --output examples/personal_assistant_public_console_probe_receipt.json --json` |
| Personal assistant public console probe validation | `python scripts/validate_personal_assistant_public_console_probe_receipt.py --receipt examples/personal_assistant_public_console_probe_receipt.json --output .change_assurance/personal_assistant_public_console_probe_validation.json --require-closed --json` |
| Personal assistant component witness | `python scripts/collect_personal_assistant_component_witness.py --output examples/personal_assistant_component_witness_receipt.json --json` |
| Personal assistant component witness validation | `python scripts/validate_personal_assistant_component_witness_receipt.py --receipt examples/personal_assistant_component_witness_receipt.json --output .change_assurance/personal_assistant_component_witness_validation.json --require-closed --json` |
| Personal assistant foundation evidence | `python scripts/collect_personal_assistant_foundation_evidence.py --output examples/personal_assistant_foundation_evidence_receipt.json --json` |
| Personal assistant foundation evidence validation | `python scripts/validate_personal_assistant_foundation_evidence_receipt.py --receipt examples/personal_assistant_foundation_evidence_receipt.json --output .change_assurance/personal_assistant_foundation_evidence_validation.json --require-closed --json` |
| Personal assistant readiness index | `python scripts/collect_personal_assistant_readiness_index.py --output examples/personal_assistant_readiness_index_receipt.json --json` |
| Personal assistant readiness index validation | `python scripts/validate_personal_assistant_readiness_index_receipt.py --receipt examples/personal_assistant_readiness_index_receipt.json --output .change_assurance/personal_assistant_readiness_index_validation.json --require-closed --json` |
| Personal assistant coherence ledger | `python scripts/collect_personal_assistant_coherence_ledger.py --output examples/personal_assistant_coherence_ledger_receipt.json --json` |
| Personal assistant coherence ledger validation | `python scripts/validate_personal_assistant_coherence_ledger_receipt.py --receipt examples/personal_assistant_coherence_ledger_receipt.json --output .change_assurance/personal_assistant_coherence_ledger_validation.json --require-closed --json` |
| Personal assistant authority coverage | `python scripts/collect_personal_assistant_authority_coverage.py --output examples/personal_assistant_authority_coverage_receipt.json --json` |
| Personal assistant authority coverage validation | `python scripts/validate_personal_assistant_authority_coverage_receipt.py --receipt examples/personal_assistant_authority_coverage_receipt.json --output .change_assurance/personal_assistant_authority_coverage_validation.json --require-closed --json` |
| Personal assistant capsule alignment | `python scripts/collect_personal_assistant_capsule_alignment.py --output examples/personal_assistant_capsule_alignment_receipt.json --json` |
| Personal assistant capsule alignment validation | `python scripts/validate_personal_assistant_capsule_alignment_receipt.py --receipt examples/personal_assistant_capsule_alignment_receipt.json --output .change_assurance/personal_assistant_capsule_alignment_validation.json --require-closed --json` |
| Personal assistant policy matrix | `python scripts/collect_personal_assistant_policy_matrix.py --output examples/personal_assistant_policy_matrix_receipt.json --json` |
| Personal assistant policy matrix validation | `python scripts/validate_personal_assistant_policy_matrix_receipt.py --receipt examples/personal_assistant_policy_matrix_receipt.json --output .change_assurance/personal_assistant_policy_matrix_validation.json --require-closed --json` |
| Personal assistant runtime boundary | `python scripts/collect_personal_assistant_runtime_boundary.py --output examples/personal_assistant_runtime_boundary_receipt.json --json` |
| Personal assistant runtime boundary validation | `python scripts/validate_personal_assistant_runtime_boundary_receipt.py --receipt examples/personal_assistant_runtime_boundary_receipt.json --output .change_assurance/personal_assistant_runtime_boundary_validation.json --require-closed --json` |
| Personal assistant foundation closure packet | `python scripts/collect_personal_assistant_foundation_closure_packet.py --output examples/personal_assistant_foundation_closure_packet.json --json` |
| Personal assistant foundation closure packet validation | `python scripts/validate_personal_assistant_foundation_closure_packet.py --packet examples/personal_assistant_foundation_closure_packet.json --output .change_assurance/personal_assistant_foundation_closure_packet_validation.json --require-closed --json` |
