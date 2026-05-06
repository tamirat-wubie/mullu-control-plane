"""Purpose: generate the proof coverage matrix witness.

Governance scope: records request-proof, action-proof, runtime-witness, and
audit-chain coverage for externally callable control-plane surfaces.
Dependencies: repository source tree, route decorators, JSON serialization.
Invariants: generated output is deterministic; representative HTTP routes map
to declared application routes or explicit wildcard families.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"
ASSURANCE_OUTPUT = REPO_ROOT / ".change_assurance" / "proof_coverage_matrix.json"
ROUTE_PATTERN = re.compile(r"@(?:router|app)\.(?:get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']")
ROUTER_PREFIX_PATTERN = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']")
FRAMEWORK_GENERATED_ROUTES = frozenset({"/docs", "/openapi.json", "/redoc"})
COVERAGE_LEVELS = ["gap", "read_model", "request_proof", "action_proof", "audit_chain"]
COVERAGE_STATES = ["proven", "witnessed", "unproven"]


def _surface(
    surface_id: str,
    paths: list[str],
    request_proof: str,
    action_proof: str,
    audit: str,
    coverage_state: str,
    evidence_files: list[str],
    notes: str,
    runtime_witnesses: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "surface_id": surface_id,
        "representative_paths": paths,
        "request_proof": request_proof,
        "action_proof": action_proof,
        "audit": audit,
        "coverage_state": coverage_state,
        "evidence_files": evidence_files,
        "notes": notes,
        "runtime_witnesses": runtime_witnesses or [],
    }


def proof_coverage_matrix() -> dict[str, Any]:
    gateway_witnesses = [
        "command_lifecycle_events_are_hash_linked",
        "terminal_closure_requires_evidence_refs",
        "successful_response_is_bound_to_response_evidence_closure",
    ]
    surfaces = [
        _surface(
            "gateway_capability_fabric",
            [
                "/webhook/*",
                "/capability-fabric/read-model",
                "/commands/{command_id}/closure",
                "DomainCapsuleCompiler.compile",
                "install_certified_capsule_with_handoff_evidence",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/server.py",
                "gateway/capability_fabric.py",
                "gateway/capability_capsule_installer.py",
                "mcoi/mcoi_runtime/core/command_capability_admission.py",
                "mcoi/mcoi_runtime/core/domain_capsule_compiler.py",
                "tests/test_gateway/test_capability_capsule_installer.py",
                "tests/test_governed_capability_fabric.py",
            ],
            "Gateway command admission, request receipt envelopes, terminal closure, capsule compiler certification-evidence manifests, and the capsule admission installer receipt expose runtime witnesses.",
            [
                *gateway_witnesses,
                "capsule_compiler_emits_certification_evidence_manifest",
                "capsule_installer_stamps_admission_receipt",
                "physical_capsule_admission_runs_promotion_preflight",
            ],
        ),
        _surface(
            "llm_streaming",
            ["/api/v1/stream", "/api/v1/chat/stream"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/app/streaming.py",
                "mcoi/tests/test_streaming.py",
                "mcoi/tests/test_server_phase200.py",
                "schemas/streaming_budget_enforcement.schema.json",
                "docs/41_streaming_budget_enforcement.md",
            ],
            "SSE responses include precharge, first-byte, chunk-debit, and final-reconcile proof identifiers.",
        ),
        _surface(
            "llm_completion",
            ["/api/v1/complete", "/api/v1/complete/safe", "/api/v1/complete/auto"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
            ],
            "Completion routes are governed through budget, model routing, and proof bridge checks.",
        ),
        _surface(
            "llm_chat_workflow",
            ["/api/v1/chat", "/api/v1/chat/workflow", "/api/v1/chat/workflow/history"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
            ],
            "Chat and workflow routes preserve governed request and action proof boundaries.",
        ),
        _surface(
            "cost_budget_read_models",
            [
                "/api/v1/budget",
                "/api/v1/costs",
                "/api/v1/costs/by-model",
                "/api/v1/costs/top-spenders",
                "/api/v1/costs/{tenant_id}",
                "/api/v1/costs/{tenant_id}/projection",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm.py",
                "mcoi/mcoi_runtime/governance/guards/budget.py",
            ],
            "Budget and cost surfaces expose bounded read models over governed spend state.",
        ),
        _surface(
            "model_experiment_control",
            ["/api/v1/models", "/api/v1/ab-test", "/api/v1/ab-test/summary"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            ["mcoi/mcoi_runtime/app/routers/llm.py"],
            "Model catalog and experiment control routes are declared as governed control surfaces.",
        ),
        _surface(
            "policy_version_registry",
            [
                "/api/v1/policies/{policy_id}/versions",
                "/api/v1/policies/{policy_id}/versions/{version}",
                "/api/v1/policies/{policy_id}/versions/{version}/promote",
                "/api/v1/policies/{policy_id}/rollback",
                "/api/v1/policies/{policy_id}/diff",
                "/api/v1/policies/{policy_id}/shadow/{shadow_version}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/policy_versions.py",
                "mcoi/mcoi_runtime/governance/policy/versioning.py",
                "mcoi/tests/test_policy_version_endpoints.py",
                "mcoi/tests/test_policy_versioning.py",
            ],
            "Policy version routes expose immutable artifact registration, promotion, rollback, diff, and shadow evaluation.",
        ),
        _surface(
            "pilot_provisioning",
            [
                "/api/v1/pilots/provision",
                "/api/v1/pilots/provisions",
                "/api/v1/pilots/provisions/{pilot_id}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/pilot.py",
                "mcoi/mcoi_runtime/app/pilot_init.py",
                "mcoi/tests/test_pilot_init.py",
                "docs/47_one_command_pilot_bringup.md",
            ],
            "Pilot provisioning returns deterministic scaffold artifacts, persists accepted provision records, and exposes bounded operator history read models.",
        ),
        _surface(
            "hosted_demo_sandbox",
            [
                "/api/v1/sandbox/summary",
                "/api/v1/sandbox/traces",
                "/api/v1/sandbox/lineage/{trace_id}",
                "/api/v1/sandbox/policy-evaluations",
            ],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/sandbox.py",
                "mcoi/mcoi_runtime/core/hosted_demo_sandbox.py",
                "mcoi/tests/test_hosted_demo_sandbox.py",
                "docs/48_hosted_demo_sandbox.md",
            ],
            "Hosted demo sandbox exposes deterministic read-only traces, lineage projections, and policy evaluations without runtime mutation.",
        ),
        _surface(
            "federated_control_plane",
            ["/api/v1/federation/summary"],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/federation.py",
                "mcoi/mcoi_runtime/core/federated_control_plane.py",
                "mcoi/tests/test_federated_control_plane.py",
                "docs/51_federated_control_plane.md",
            ],
            "Federated control-plane summary exposes signed policy distribution and local enforcement receipts without tenant data replication.",
        ),
        _surface(
            "finance_approval_packets",
            [
                "/api/v1/finance/approval-packets",
                "/api/v1/finance/approval-packets/operator/read-model",
                "/api/v1/finance/approval-packets/{case_id}",
                "/api/v1/finance/approval-packets/{case_id}/approval",
                "/api/v1/finance/approval-packets/{case_id}/proof",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/finance_approval.py",
                "mcoi/mcoi_runtime/contracts/finance_approval_packet.py",
                "mcoi/mcoi_runtime/core/finance_approval/policy.py",
                "mcoi/mcoi_runtime/core/finance_approval/state_machine.py",
                "mcoi/mcoi_runtime/core/finance_approval/proof.py",
                "mcoi/tests/test_finance_approval_packet.py",
                "mcoi/tests/test_finance_approval_router.py",
                "examples/finance_approval_packet_blocked.json",
                "examples/finance_approval_packet_success.json",
            ],
            "Finance approval packet routes create policy-evaluated packet read models, expose a bounded operator read model, record explicit approval/effect receipts, and export bounded packet proofs for review-bound or closed cases.",
            [
                "finance_packet_policy_reasons_explicit",
                "blocked_packet_emits_no_effect",
                "approval_action_binds_approval_effect_and_closure_refs",
                "packet_proof_requires_policy_evidence_and_closure_for_closed_states",
                "operator_read_model_bounds_visible_packets_and_counts",
            ],
        ),
        _surface(
            "data_governance_controls",
            [
                "/api/v1/data-governance/summary",
                "/api/v1/data-governance/classify",
                "/api/v1/data-governance/policies",
                "/api/v1/data-governance/residency-constraints",
                "/api/v1/data-governance/privacy-rules",
                "/api/v1/data-governance/redaction-rules",
                "/api/v1/data-governance/retention-rules",
                "/api/v1/data-governance/evaluate",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data.py",
                "mcoi/mcoi_runtime/core/data_governance.py",
                "mcoi/mcoi_runtime/contracts/data_governance.py",
                "mcoi/tests/test_data_governance_endpoints.py",
                "mcoi/tests/test_data_governance_engine.py",
                "mcoi/tests/test_data_governance_integration.py",
            ],
            "Data governance routes bind classification, policy, residency, privacy, redaction, retention, and handling evaluation decisions to governed responses with action proof receipts and state-hash posture witnesses.",
            [
                "data_governance_state_hash",
                "data_governance_action_proof",
                "tenant_visible_violation_read_model",
            ],
        ),
        _surface(
            "compliance_evidence_exports",
            [
                "/api/v1/compliance/audit-package",
                "/api/v1/compliance/incident-package",
                "/api/v1/compliance/mapping",
                "/api/v1/compliance/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/compliance.py",
                "mcoi/tests/test_compliance_export.py",
                "mcoi/tests/test_compliance_alignment_matrix.py",
                "scripts/compliance_alignment_matrix.py",
                "docs/50_compliance_alignment_mapping.md",
            ],
            "Compliance export routes emit bounded evidence packages with package hashes, audit-chain verification, supported-framework boundaries, and self-audited export events.",
            [
                "compliance_package_hash",
                "audit_chain_verification",
                "self_audited_export_event",
            ],
        ),
        _surface(
            "audit_chain_api",
            [
                "/api/v1/audit",
                "/api/v1/audit/verify",
                "/api/v1/audit/summary",
                "/api/v1/audit/anchor",
                "/api/v1/audit/anchor/{anchor_id}/verify",
                "/api/v1/audit/anchors",
            ],
            "read_model",
            "request_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/audit.py",
                "mcoi/mcoi_runtime/governance/audit/trail.py",
                "mcoi/mcoi_runtime/governance/audit/anchor.py",
                "mcoi/tests/test_audit_trail.py",
                "mcoi/tests/test_v4_28_audit_checkpoint.py",
                "mcoi/tests/test_server_phase202.py",
                "mcoi/tests/test_production_truth.py",
            ],
            "Audit routes expose bounded audit entries, chain verification, summaries, checkpoint anchoring, anchor verification, and anchor history with hash-chain witnesses.",
            [
                "audit_chain_verify_endpoint",
                "audit_summary_read_model",
                "audit_anchor_checkpoint_created",
                "audit_anchor_verification_endpoint",
                "audit_anchor_history_read_model",
                "audit_chain_hash_linked",
            ],
        ),
        _surface(
            "runbook_learning_lifecycle",
            [
                "/api/v1/runbooks",
                "/api/v1/runbooks/analyze",
                "/api/v1/runbooks/approve",
                "/api/v1/runbooks/patterns",
                "/api/v1/runbooks/promote",
                "/api/v1/runbooks/summary",
                "/api/v1/runbooks/{runbook_id}/activate",
                "/api/v1/runbooks/{runbook_id}/retire",
                "/api/v1/mil-audit/admit-runbook",
                "/api/v1/mil-audit/runbooks",
                "/api/v1/mil-audit/runbooks/{runbook_id}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/runbooks.py",
                "mcoi/mcoi_runtime/app/routers/mil_audit.py",
                "mcoi/mcoi_runtime/core/runbook_learning.py",
                "mcoi/mcoi_runtime/app/server_http.py",
                "mcoi/tests/test_mil_audit_router.py",
                "mcoi/tests/test_runbook_learning.py",
                "examples/mil_audit_runbook_operator_checklist.json",
                "scripts/validate_mil_audit_runbook_operator_checklist.py",
                "scripts/preflight_mil_audit_runbook_workflow.py",
                "tests/test_validate_mil_audit_runbook_operator_checklist.py",
                "tests/test_preflight_mil_audit_runbook_workflow.py",
            ],
            "Runbook learning lifecycle routes derive candidate runbooks from audit-trail patterns and MIL audit replay bundles, require explicit promotion and operator approval before activation, gate retirement by active state, emit governed sanitized errors, expose bounded read models for runbooks, patterns, and summaries, and provide a checklist-backed MIL audit runbook preflight.",
            [
                "patterns_detected_from_audit_trail",
                "promotion_requires_detected_pattern",
                "approval_required_before_activation",
                "retirement_requires_active_runbook",
                "promote_and_approve_audit_records",
                "mil_audit_replay_admits_runbook",
                "mil_audit_operator_checklist_validated",
                "mil_audit_runbook_preflight_ready",
                "sanitized_runbook_error_details",
                "runbook_pattern_read_models_bounded",
                "runbook_responses_governed",
            ],
        ),
        _surface(
            "gateway_webhook_ingress",
            ["/webhook/web", "/webhook/slack", "/webhook/telegram"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/router.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Webhook ingress binds tenant resolution, command ledger, and event-log evidence.",
        ),
        _surface(
            "gateway_approval_resolution",
            ["/webhook/approve/{request_id}", "/authority/approval-chains"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/approval.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Approval resolution exposes protected operator paths and audited chain state.",
        ),
        _surface(
            "authority_obligation_mesh",
            ["/authority/witness", "/authority/responsibility", "/authority/obligations", "/authority/escalations"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/authority_obligation_mesh.py",
                "tests/test_gateway/test_authority_obligation_mesh.py",
            ],
            "Authority and obligation surfaces expose unresolved responsibility state.",
            [
                "pending_approval_chain_count",
                "open_obligation_count",
                "overdue_obligation_count",
                "escalated_obligation_count",
            ],
        ),
        _surface(
            "authority_operator_controls",
            [
                "/authority/operator",
                "/authority/operator-audit",
                "/authority/ownership",
                "/authority/policies",
                "/authority/approval-chains/expire-overdue",
                "/authority/obligations/{obligation_id}/satisfy",
                "/authority/obligations/escalate-overdue",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/authority_obligation_mesh.py",
                "gateway/tenant_identity.py",
                "scripts/collect_runtime_conformance.py",
                "tests/test_gateway/test_webhooks.py",
                "tests/test_gateway/test_authority_obligation_mesh.py",
            ],
            "Authority operator controls bind guarded operator access, audit events, ownership and policy read models, overdue approval expiration, and obligation satisfaction/escalation controls.",
            [
                "operator_access_guard",
                "operator_audit_events",
                "ownership_policy_read_models",
                "approval_expiration_witness",
                "obligation_satisfaction_escalation_witness",
            ],
        ),
        _surface(
            "gateway_runtime_witness",
            ["/gateway/witness", "/runtime/witness", "/anchors/latest"],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                ".github/workflows/gateway-publication.yml",
                "scripts/orchestrate_deployment_witness.py",
                "scripts/preflight_deployment_witness.py",
                "scripts/collect_deployment_witness.py",
                "scripts/validate_deployment_publication_closure.py",
                "scripts/validate_mcp_capability_manifest.py",
                "scripts/validate_mcp_operator_checklist.py",
                "scripts/validate_gateway_publication_receipt.py",
                "scripts/validate_deployment_orchestration_receipt.py",
                "schemas/deployment_publication_closure_validation.schema.json",
                "schemas/deployment_orchestration_receipt.schema.json",
                "schemas/deployment_orchestration_receipt_validation.schema.json",
                "schemas/gateway_publication_readiness.schema.json",
                "schemas/gateway_publication_receipt_validation.schema.json",
                "schemas/deployment_witness.schema.json",
                "schemas/mullu_governance_protocol.manifest.json",
                "tests/test_orchestrate_deployment_witness.py",
                "tests/test_report_gateway_publication_readiness.py",
                "tests/test_validate_gateway_publication_receipt.py",
                "tests/test_validate_deployment_orchestration_receipt.py",
                "tests/test_validate_deployment_publication_closure.py",
                "tests/test_validate_protocol_manifest.py",
                "tests/test_preflight_deployment_witness.py",
                "tests/test_collect_deployment_witness.py",
                "tests/test_validate_deployment_publication_closure.py",
            ],
            "Runtime witness surfaces publish bounded operational and responsibility debt state; deployment witnesses require raw runtime and authority debt-clear evidence before publication closure, and orchestration receipts bind ingress render, MCP checklist validation, preflight, dispatch evidence, schema contract validation, and post-run receipt validation before deployment witness readiness.",
            [
                "latest_command_event_hash",
                "latest_terminal_certificate_id",
                "responsibility_debt_clear",
                "runtime_responsibility_debt_clear",
                "open_obligation_count",
                "overdue_obligation_count",
                "authority_responsibility_debt_clear",
                "authority_overdue_approval_chain_count",
                "authority_overdue_obligation_count",
                "authority_escalated_obligation_count",
                "authority_unowned_high_risk_capability_count",
                "deployment_witness_orchestration_receipt",
                "deployment_publication_closure_validation_schema",
                "deployment_orchestration_validation_schema",
                "gateway_publication_readiness_schema",
                "gateway_publication_receipt_validation_schema",
            ],
        ),
        _surface(
            "runtime_conformance_attestation",
            ["/runtime/conformance"],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/conformance.py",
                "gateway/physical_worker_canary.py",
                "scripts/collect_runtime_conformance.py",
                "scripts/produce_physical_worker_canary.py",
                "scripts/validate_mcp_capability_manifest.py",
                "schemas/runtime_conformance_certificate.schema.json",
                "tests/test_gateway/test_conformance.py",
                "tests/test_collect_runtime_conformance.py",
                "tests/test_produce_physical_worker_canary.py",
            ],
            "Runtime conformance certificate binds live witness, closure, fabric, isolation, lineage, authority, physical worker canary proof, MCP manifest validity, proof-matrix route classification summary, document-drift checks, issuer schema self-validation, and collector schema validation into one signed attestation.",
            [
                "gateway_witness_valid",
                "runtime_witness_valid",
                "runtime_conformance_certificate_schema_valid",
                "runtime_conformance_collector_schema_valid",
                "proof_coverage_unclassified_routes_reported",
                "command_closure_canary_passed",
                "capability_admission_canary_passed",
                "dangerous_capability_isolation_canary_passed",
                "lineage_query_canary_passed",
                "authority_responsibility_debt_clear",
                "authority_directory_sync_receipt_valid",
                "capability_plan_bundle_canary_passed",
                "physical_worker_canary_passed",
                "physical_worker_canary_artifact_hash_bound",
            ],
        ),
        _surface(
            "production_evidence_plane",
            [
                "/deployment/witness",
                "/capabilities/evidence",
                "/audit/verify",
                "/proof/verify",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "scripts/collect_deployment_witness.py",
                ".github/workflows/deployment-witness.yml",
                "schemas/production_evidence_witness.schema.json",
                "schemas/capability_evidence_endpoint.schema.json",
                "schemas/audit_verification_endpoint.schema.json",
                "schemas/proof_verification_endpoint.schema.json",
                "tests/test_gateway/test_production_evidence.py",
                "tests/test_collect_deployment_witness.py",
            ],
            "Production evidence endpoints expose signed deployment posture, capability evidence, audit verification, and proof verification; deployment witness collection can require the whole plane before publication, derives live physical safety evidence only from certified registry extensions, and blocks live physical capability claims without explicit safety evidence while allowing sandbox-only physical canary evidence.",
            [
                "signed_production_evidence_witness",
                "capability_evidence_schema_valid",
                "audit_verification_schema_valid",
                "proof_verification_schema_valid",
                "deployment_collection_requires_production_evidence",
                "live_physical_safety_evidence_derived_from_registry",
                "live_physical_capability_requires_safety_evidence",
                "sandbox_physical_capability_remains_non_production",
                "missing_production_evidence_fails_closed",
            ],
        ),
        _surface(
            "runtime_reflex_engine",
            [
                "/runtime/self/health",
                "/runtime/self/inspect",
                "/runtime/self/diagnose",
                "/runtime/self/evaluate",
                "/runtime/self/propose-upgrade",
                "/runtime/self/certify",
                "/runtime/self/promote",
                "/runtime/self/deployment-witnesses",
                "/runtime/self/witness",
            ],
            "read_model",
            "request_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "mcoi/mcoi_runtime/contracts/reflex.py",
                "mcoi/mcoi_runtime/core/reflex.py",
                "schemas/reflex_deployment_witness_envelope.schema.json",
                "schemas/reflex_deployment_witness_validator_receipt.schema.json",
                "scripts/emit_reflex_deployment_witness_validator_receipt.py",
                "scripts/validate_reflex_deployment_witness.py",
                "tests/test_reflex_engine.py",
                "tests/test_gateway/test_reflex_endpoints.py",
                "tests/test_emit_reflex_deployment_witness_validator_receipt.py",
                "tests/test_validate_reflex_deployment_witness.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Runtime Reflex surfaces expose operator-gated health, anomaly, diagnosis, eval, proposal, certification handoff, promotion decision, signed witness projections, schema-backed offline witness replay, and CI receipt artifacts without direct runtime mutation.",
            [
                "operator_only_access",
                "mutation_applied_false",
                "certification_handoff_required",
                "protected_surfaces_auto_promote_false",
                "signed_reflex_witness",
                "reflex_deployment_witness_schema",
                "reflex_validator_receipt_schema",
                "offline_reflex_witness_replay",
                "reflex_validator_receipt_artifact",
            ],
        ),
        _surface(
            "governed_operational_intelligence",
            [
                "WorldStateStore.add_entity",
                "GoalCompiler.compile",
                "CausalSimulator.simulate",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/world_state.py",
                "gateway/goal_compiler.py",
                "gateway/causal_simulator.py",
                "schemas/world_state.schema.json",
                "schemas/goal.schema.json",
                "schemas/simulation_receipt.schema.json",
                "tests/test_gateway/test_world_state.py",
                "tests/test_gateway/test_goal_compiler.py",
                "tests/test_gateway/test_causal_simulator.py",
            ],
            "Governed operational intelligence binds sourced world-state admission, compiled goal-plan certificates, and deterministic causal simulation receipts before effect-bearing execution.",
            [
                "world_assertions_require_source_evidence",
                "goal_plan_certificate_hash_bound",
                "simulation_receipt_schema_valid",
                "open_world_contradictions_block_execution",
                "high_risk_controls_projected_before_execution",
            ],
        ),
        _surface(
            "capability_forge",
            [
                "CapabilityForge.create_candidate",
                "CapabilityForge.validate",
                "CapabilityForge.build_certification_handoff",
                "install_certification_handoff_evidence",
                "install_certification_handoff_evidence_batch",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/capability_forge.py",
                "schemas/capability_candidate.schema.json",
                "tests/test_gateway/test_capability_forge.py",
            ],
            "Capability forge emits schema-backed candidate packages and maturity-ready certification handoffs only, keeps promotion blocked, validates approval, sandbox, receipt, eval, live-write, and recovery evidence before certification handoff, installs certified handoffs as certification evidence without direct maturity overrides, and batches handoff evidence with exact capsule-entry coverage before registry admission.",
            [
                "candidate_promotion_blocked",
                "candidate_schema_valid",
                "candidate_certification_handoff_emits_maturity_bundle",
                "certification_handoff_installs_evidence_without_maturity_claim",
                "certification_handoff_batch_preserves_capsule_admission_gate",
                "high_risk_approval_policy_required",
                "effect_bearing_candidate_requires_sandbox",
                "effect_bearing_candidate_requires_recovery_path",
            ],
        ),
        _surface(
            "capability_maturity_assessment",
            [
                "CapabilityMaturityEvidenceSynthesizer.materialize_extension",
                "CapabilityMaturityAssessor.assess",
                "CapabilityRegistryMaturityProjector.decorate_read_model",
                "MaturityProjectingCapabilityAdmissionGate.read_model",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "capabilities/connector/capability_pack.json",
                "capabilities/financial/capability_pack.json",
                "docs/39_governed_capability_fabric.md",
                "gateway/capability_fabric.py",
                "gateway/capability_maturity.py",
                "gateway/operator_capability_console.py",
                "schemas/capability_maturity.schema.json",
                "schemas/README.md",
                "tests/test_gateway/test_capability_fabric.py",
                "tests/test_gateway/test_capability_maturity.py",
                "tests/test_gateway/test_operator_capability_console.py",
            ],
            "Capability maturity assessment derives C0-C7 readiness from explicit evidence, synthesizes maturity extensions from certification evidence bundles, projects maturity onto capability fabric read models, includes read-only and effect-bearing default-pack C6 examples, blocks production overclaims until live and recovery evidence are complete, and blocks autonomy overclaims until bounded autonomy controls are present.",
            [
                "certification_evidence_synthesizes_maturity_extension",
                "maturity_derived_from_evidence",
                "registry_read_model_exposes_maturity",
                "default_pack_C6_examples_projected",
                "effect_bearing_production_requires_live_write",
                "production_requires_worker_deployment_recovery",
                "autonomy_requires_C7_controls",
                "capability_maturity_schema_valid",
            ],
        ),
        _surface(
            "networked_worker_mesh",
            [
                "NetworkedWorkerMesh.register_worker",
                "NetworkedWorkerMesh.dispatch",
                "NetworkedWorkerMesh.read_model",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/physical_action_boundary.py",
                "gateway/physical_worker_canary.py",
                "gateway/worker_mesh.py",
                "scripts/produce_physical_worker_canary.py",
                "schemas/physical_action_receipt.schema.json",
                "schemas/worker_mesh.schema.json",
                "tests/test_gateway/test_physical_action_boundary.py",
                "tests/test_gateway/test_physical_worker_canary.py",
                "tests/test_gateway/test_worker_mesh.py",
                "tests/test_produce_physical_worker_canary.py",
            ],
            "Networked worker mesh dispatches only through active leases, rejects tenant/capability/operation/budget violations before handler execution, requires admitted physical action receipts for physical workers, and emits schema-backed receipts that explicitly require terminal closure.",
            [
                "active_lease_required",
                "tenant_capability_operation_budget_checked",
                "forbidden_operations_override_allowed",
                "physical_action_receipt_required_for_physical_workers",
                "physical_worker_canary_blocks_without_receipt",
                "physical_worker_canary_passed",
                "physical_worker_canary_uses_sandbox_handler",
                "worker_evidence_refs_required",
                "worker_receipt_not_terminal_closure",
                "worker_mesh_schema_valid",
            ],
        ),
        _surface(
            "agent_identity",
            [
                "AgentIdentityRegistry.register",
                "AgentIdentityRegistry.evaluate",
                "AgentIdentityRegistry.record_outcome",
                "AgentIdentity",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/agent_identity.py",
                "schemas/agent_identity.schema.json",
                "tests/test_gateway/test_agent_identity.py",
            ],
            "Agent identity binds user-owned agents to owner, tenant, role, capability scopes, budget, memory scope, approval scope, delegation scope, evidence history, and reputation.",
            [
                "owner_tenant_identity_required",
                "capability_scope_conflict_denied",
                "self_approval_forbidden",
                "policy_mutation_forbidden",
                "delegation_requires_lease",
                "agent_budget_enforced",
                "reputation_update_requires_evidence",
                "agent_identity_schema_valid",
            ],
        ),
        _surface(
            "claim_verification",
            [
                "ClaimVerificationEngine.verify",
                "ClaimNode",
                "ClaimVerificationReport",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/claim_verification.py",
                "schemas/claim_verification_report.schema.json",
                "tests/test_gateway/test_claim_verification.py",
            ],
            "Claim verification reports distinguish observed facts, user claims, model inferences, external source claims, verified results, stale results, and contradicted results before planning or execution use.",
            [
                "claim_type_declared",
                "source_evidence_required",
                "contradictions_block_execution",
                "stale_claims_block_execution",
                "high_risk_requires_independent_support",
                "claim_verification_schema_valid",
            ],
        ),
        _surface(
            "connector_self_healing",
            [
                "ConnectorSelfHealingEngine.evaluate",
                "ConnectorFailure",
                "ConnectorHealingReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/connector_self_healing.py",
                "schemas/connector_self_healing_receipt.schema.json",
                "tests/test_gateway/test_connector_self_healing.py",
            ],
            "Connector self-healing emits bounded non-terminal recovery receipts for provider failures, retries, fallback providers, read-only degradation, incident opening, and capability revocation.",
            [
                "provider_success_not_assumed",
                "write_failures_require_operator_review",
                "missing_receipt_revokes_capability",
                "fallback_provider_requires_certification",
                "read_only_degradation_bounded",
                "connector_self_healing_schema_valid",
            ],
        ),
        _surface(
            "collaboration_cases",
            [
                "CollaborationCaseManager.open_case",
                "CollaborationCaseManager.close_case",
                "CollaborationControl",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/collaboration_cases.py",
                "schemas/collaboration_case.schema.json",
                "tests/test_gateway/test_collaboration_cases.py",
            ],
            "Collaboration cases bind requester separation, approval controls, decider authority, evidence hashing, and non-terminal case closure into governed operational casework.",
            [
                "approval_separation_required",
                "pending_controls_block_case_closure",
                "decider_authority_required",
                "case_closure_not_terminal_command_closure",
                "collaboration_case_schema_valid",
            ],
        ),
        _surface(
            "capability_maturity",
            [
                "CapabilityMaturityAssessor.assess",
                "CapabilityMaturityAssessment",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/capability_maturity.py",
                "schemas/capability_maturity.schema.json",
                "tests/test_gateway/test_capability_maturity.py",
            ],
            "Capability maturity derives production and autonomy readiness from explicit evidence, reports missing C6/C7 proof, and rejects overclaimed autonomy states.",
            [
                "maturity_derived_from_evidence",
                "effect_bearing_c6_requires_live_write",
                "production_requires_c6_or_c7",
                "autonomy_requires_c7",
                "capability_maturity_schema_valid",
            ],
        ),
        _surface(
            "policy_prover",
            [
                "PolicyProver.prove",
                "PolicyProofReport",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/policy_prover.py",
                "schemas/policy_proof_report.schema.json",
                "tests/test_gateway/test_policy_prover.py",
            ],
            "Policy prover evaluates modeled execution paths against named safety properties and emits schema-backed counterexamples for reachable bypasses.",
            [
                "payment_requires_approval_counterexample",
                "tenant_isolation_counterexample",
                "shell_requires_sandbox_counterexample",
                "provider_url_approved_counterexample",
                "memory_requires_admission_counterexample",
                "unknown_property_fails_closed",
                "policy_proof_report_schema_valid",
            ],
        ),
        _surface(
            "memory_lattice",
            [
                "MemoryLatticeGate.assess",
                "MemoryLatticeAdmission",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/memory_lattice.py",
                "schemas/memory_lattice.schema.json",
                "tests/test_gateway/test_memory_lattice.py",
            ],
            "Memory lattice admission derives planning and execution use from evidence, learning admission, policy authority, freshness, scope, and contradiction state.",
            [
                "raw_event_memory_not_directly_admitted",
                "semantic_memory_requires_learning_admission",
                "policy_memory_requires_authority_ref",
                "preference_memory_tenant_owner_scoped",
                "contradiction_and_stale_memory_block_execution",
                "memory_lattice_schema_valid",
            ],
        ),
        _surface(
            "workflow_mining",
            [
                "WorkflowMiningEngine.mine",
                "WorkflowMiningReport",
                "WorkflowDraft",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/workflow_mining.py",
                "schemas/workflow_mining_report.schema.json",
                "tests/test_gateway/test_workflow_mining.py",
            ],
            "Workflow mining detects repeated human traces and emits governed draft templates that remain blocked until sandbox replay and operator review.",
            [
                "repeated_trace_pattern_required",
                "workflow_draft_activation_blocked",
                "operator_review_required",
                "sandbox_replay_required",
                "risky_pattern_requires_approval_rules",
                "workflow_mining_report_schema_valid",
            ],
        ),
        _surface(
            "trust_ledger",
            [
                "TrustLedger.issue",
                "TrustLedger.verify",
                "TrustLedger.anchor_bundle",
                "TrustLedger.verify_anchor_receipt",
                "GET /evidence/bundles/{command_id}",
                "scripts/verify_evidence_bundle.py",
                "TrustLedgerBundle",
                "ExternalProofAnchorReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/evidence_bundle.py",
                "gateway/trust_ledger.py",
                "scripts/verify_evidence_bundle.py",
                "schemas/trust_ledger_anchor_receipt.schema.json",
                "schemas/trust_ledger_bundle.schema.json",
                "tests/test_gateway/test_evidence_bundle_endpoint.py",
                "tests/test_gateway/test_trust_ledger_anchor_receipt.py",
                "tests/test_gateway/test_trust_ledger.py",
            ],
            "Trust ledger signs terminal-closure evidence bundles, exposes operator bundle export, verifies exported bundle files offline, and emits external anchor receipts that bind typed artifact roots, tenant, command, deployment, commit, hash-chain root, and external anchor state.",
            [
                "terminal_certificate_id_required",
                "evidence_refs_required",
                "evidence_bundle_endpoint_requires_terminal_certificate",
                "offline_bundle_verifier_validates_schema_hash_and_signature",
                "bundle_hash_tamper_detection",
                "hmac_signature_verification",
                "anchored_bundle_requires_external_anchor_ref",
                "typed_artifact_root_required",
                "anchor_receipt_hmac_verification",
                "anchor_receipt_schema_valid",
                "anchor_receipt_non_terminal_marker_required",
                "trust_ledger_bundle_schema_valid",
            ],
        ),
        _surface(
            "domain_operating_pack",
            [
                "DomainOperatingPackCompiler.compile",
                "DomainOperatingPackCompiler.validate",
                "DomainOperatingPackCatalog",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/domain_operating_pack.py",
                "schemas/domain_operating_pack.schema.json",
                "tests/test_gateway/test_domain_operating_pack.py",
            ],
            "Domain operating packs compile governed buyer-facing solution bundles that remain activation-blocked until certification evidence is present.",
            [
                "builtin_domain_pack_catalog_complete",
                "finance_ops_pack_declares_governed_artifacts",
                "high_risk_pack_requires_approval_roles",
                "certified_pack_requires_evidence_refs",
                "domain_operating_pack_schema_valid",
            ],
        ),
        _surface(
            "multimodal_operating_layer",
            [
                "MultimodalOperatingLayer.evaluate",
                "MultimodalOperationReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/multimodal_operating_layer.py",
                "schemas/multimodal_operation_receipt.schema.json",
                "tests/test_gateway/test_multimodal_operating_layer.py",
            ],
            "Multimodal operating layer emits source-bound pre-dispatch receipts and blocks unsafe modality worker effects before execution.",
            [
                "multimodal_receipt_schema_valid",
                "external_send_blocked_by_default",
                "sensitive_voice_requires_redaction_evidence",
                "unknown_modality_fails_closed",
            ],
        ),
        _surface(
            "physical_action_boundary",
            [
                "PhysicalActionBoundary.evaluate",
                "PhysicalActionRequest",
                "PhysicalActionReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "capsules/physical.json",
                "capabilities/physical/capability_pack.json",
                "gateway/capability_capsule_installer.py",
                "gateway/physical_action_boundary.py",
                "gateway/physical_worker_canary.py",
                "scripts/preflight_physical_capability_promotion.py",
                "scripts/produce_physical_worker_canary.py",
                "schemas/physical_action_receipt.schema.json",
                "tests/test_gateway/test_capability_capsule_installer.py",
                "tests/test_gateway/test_physical_action_boundary.py",
                "tests/test_gateway/test_physical_capability_pack.py",
                "tests/test_gateway/test_physical_worker_canary.py",
                "tests/test_preflight_physical_capability_promotion.py",
                "tests/test_produce_physical_worker_canary.py",
            ],
            "Physical action boundary emits schema-backed pre-dispatch receipts that block physical-world side effects unless hardware identity, safety envelope, manual override, emergency stop, simulation, operator approval, sensor confirmation, and safe-state controls are present; checked-in physical capability fixtures stay outside default loading, admit sandbox replay only when production readiness is not required, reject live physical promotion by default, and require promotion preflight evidence before any live production claim.",
            [
                "physical_action_receipt_schema_valid",
                "physical_capability_pack_fixture_not_default_loaded",
                "physical_sandbox_replay_admitted_without_production_gate",
                "live_physical_capability_rejected_by_production_gate",
                "physical_pack_projects_sandbox_only_evidence",
                "physical_promotion_preflight_blocks_fixture_live_claim",
                "physical_promotion_preflight_requires_live_safety_evidence",
                "physical_promotion_preflight_accepts_full_evidence",
                "physical_promotion_preflight_allows_sandbox_only_pack",
                "physical_capsule_admission_runs_promotion_preflight",
                "physical_capsule_admission_keeps_registry_unmutated_on_preflight_failure",
                "hardware_identity_required",
                "safety_envelope_required",
                "manual_override_required",
                "emergency_stop_required",
                "simulation_pass_required",
                "operator_approval_required",
                "sensor_confirmation_required",
                "physical_dispatch_blocked_until_controls_complete",
                "physical_worker_canary_uses_sandbox_handler",
                "physical_worker_canary_artifact_hash_bound",
            ],
        ),
        _surface(
            "temporal_kernel",
            [
                "/api/v1/temporal/schedules",
                "/api/v1/temporal/schedules/{schedule_id}",
                "/api/v1/temporal/schedules/{schedule_id}/cancel",
                "/api/v1/temporal/worker/tick",
                "/api/v1/temporal/summary",
                "TemporalKernel.evaluate",
                "TrustedClock.now_utc",
                "TrustedClock.monotonic_ns",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_kernel.py",
                "mcoi/mcoi_runtime/app/routers/temporal_scheduler.py",
                "mcoi/mcoi_runtime/core/temporal_scheduler.py",
                "mcoi/mcoi_runtime/core/temporal_scheduler_worker.py",
                "mcoi/mcoi_runtime/persistence/temporal_scheduler_store.py",
                "schemas/temporal_operation_receipt.schema.json",
                "tests/test_gateway/test_temporal_kernel.py",
                "mcoi/tests/test_temporal_scheduler_router.py",
            ],
            "Temporal kernel owns runtime time truth for schedules, expiry, approval validity, evidence freshness, budget windows, causal prerequisites, temporal schedule APIs, and monotonic duration witnesses before dispatch.",
            [
                "runtime_clock_injected",
                "monotonic_duration_measured",
                "future_schedule_defers",
                "approval_expiry_denies",
                "stale_evidence_escalates",
                "budget_window_checked",
                "causal_preconditions_required",
                "temporal_scheduler_routes_governed",
                "schedule_read_models_persisted",
                "worker_tick_certifies_proofs",
                "cancel_emits_terminal_receipt",
                "temporal_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
        ),
        _surface(
            "temporal_evidence_freshness",
            [
                "TemporalEvidenceFreshness.evaluate",
                "EvidenceFreshnessClaim",
                "TemporalEvidenceFreshnessReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_evidence_freshness.py",
                "schemas/temporal_evidence_freshness_receipt.schema.json",
                "tests/test_gateway/test_temporal_evidence_freshness.py",
            ],
            "Temporal evidence freshness rechecks required evidence age, freshness windows, tenant scope, high-risk verification, revoked evidence, missing evidence, and expiring evidence before dispatch.",
            [
                "evidence_age_computed_from_runtime_clock",
                "freshness_window_required_for_dispatch",
                "stale_required_evidence_triggers_refresh",
                "missing_required_evidence_blocks_dispatch",
                "revoked_or_unverified_high_risk_evidence_blocks",
                "expiring_evidence_warns_before_dispatch",
                "temporal_evidence_freshness_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
        ),
        _surface(
            "temporal_memory",
            [
                "TemporalMemory.evaluate",
                "TemporalMemoryRecord",
                "TemporalMemoryReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_memory.py",
                "schemas/temporal_memory_receipt.schema.json",
                "tests/test_gateway/test_temporal_memory.py",
            ],
            "Temporal memory gates memory use through runtime-owned age, evidence freshness, validity windows, confidence decay, tenant-owner scope, allowed use, and supersession checks before memory can guide action.",
            [
                "memory_age_computed_from_runtime_clock",
                "stale_memory_requires_refresh",
                "validity_window_blocks_expired_memory",
                "superseded_memory_not_usable",
                "confidence_decay_blocks_weak_memory",
                "tenant_owner_scope_checked",
                "allowed_use_checked",
                "temporal_memory_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
        ),
        _surface(
            "temporal_memory_refresh",
            [
                "TemporalMemoryRefresh.evaluate",
                "MemoryRefreshRequest",
                "TemporalMemoryRefreshReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_memory_refresh.py",
                "schemas/temporal_memory_refresh_receipt.schema.json",
                "tests/test_gateway/test_temporal_memory_refresh.py",
            ],
            "Temporal memory refresh converts stale or refresh-required memory receipts into bounded refresh tasks with required evidence coverage, owner scope, review readiness, due windows, and activation blocks before refreshed memory can guide action.",
            [
                "usable_memory_does_not_create_refresh_task",
                "stale_memory_creates_bounded_refresh_task",
                "evidence_type_coverage_gates_review_readiness",
                "invalid_refresh_policy_blocks_task_creation",
                "superseded_memory_blocks_reactivation",
                "temporal_memory_refresh_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
        ),
        _surface(
            "temporal_scheduler",
            [
                "TemporalScheduler.evaluate",
                "ScheduledCommand",
                "TemporalSchedulerReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_scheduler.py",
                "schemas/temporal_scheduler_receipt.schema.json",
                "tests/test_gateway/test_temporal_scheduler.py",
            ],
            "Temporal scheduler gates scheduled command wakeups with idempotency, due checks, retry windows, missed-run receipts, lease acquisition, recurrence declaration, and high-risk approval plus temporal recheck evidence before dispatch.",
            [
                "scheduled_command_requires_execute_at",
                "idempotency_required",
                "lease_acquired_before_dispatch",
                "future_schedule_defers",
                "missed_run_receipt_emitted",
                "retry_window_checked",
                "high_risk_reapproval_required",
                "active_lease_blocks_duplicate_execution",
                "temporal_scheduler_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
        ),
        _surface(
            "policy_proof_report",
            [
                "PolicyProver.prove",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/policy_prover.py",
                "schemas/policy_proof_report.schema.json",
                "schemas/README.md",
                "tests/test_gateway/test_policy_prover.py",
            ],
            "Policy proof reports evaluate explicit invariants over bounded cases, emit concrete counterexamples, and forbid policy weakening as a proof strategy.",
            [
                "bounded_policy_cases_required",
                "empty_invariants_rejected",
                "counterexamples_are_concrete",
                "proved_report_has_no_counterexamples",
                "policy_weakening_forbidden",
                "policy_proof_schema_valid",
            ],
        ),
        _surface(
            "autonomous_capability_upgrade",
            [
                "AutonomousCapabilityUpgradeLoop.propose",
                "CapabilityHealthSignal",
                "CapabilityUpgradePlan",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/autonomous_capability_upgrade.py",
                "schemas/capability_upgrade_plan.schema.json",
                "tests/test_gateway/test_autonomous_capability_upgrade.py",
            ],
            "Autonomous capability upgrade converts health signals into activation-blocked proposals that require evals, sandbox tests, ChangeCommand, ChangeCertificate, canary, terminal closure, and learning admission before promotion.",
            [
                "health_signal_requires_evidence_refs",
                "upgrade_candidates_are_promotion_blocked",
                "critical_governance_changes_require_second_approval",
                "capability_upgrade_plan_schema_valid",
            ],
        ),
        _surface(
            "autonomous_test_generation",
            [
                "AutonomousTestGenerationEngine.generate",
                "FailureTrace",
                "TestGenerationPlan",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/autonomous_test_generation.py",
                "schemas/autonomous_test_generation_plan.schema.json",
                "tests/test_gateway/test_autonomous_test_generation.py",
            ],
            "Autonomous test generation converts certified failure traces into activation-blocked, operator-review-required replay, policy, tenant, approval, budget, and sandbox test proposals.",
            [
                "failure_trace_requires_evidence_refs",
                "high_risk_failures_generate_governance_variants",
                "plans_are_activation_blocked",
                "autonomous_test_generation_plan_schema_valid",
            ],
        ),
        _surface(
            "capability_plan_evidence_bundle",
            [
                "/capability-plans/read-model",
                "/capability-plans/{plan_id}/closure",
                "/capability-plans/{plan_id}/recover",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/plan.py",
                "gateway/plan_executor.py",
                "gateway/plan_ledger.py",
                "tests/test_gateway/test_plan.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Capability plan surfaces expose plan terminal certificates, plan evidence bundles, failure witnesses, and recovery-attempt audit records.",
            [
                "plan_terminal_certificate",
                "plan_evidence_bundle",
                "plan_witnesses",
                "plan_recovery_attempts",
            ],
        ),
        _surface(
            "replay_determinism",
            ["/api/v1/replay/{trace_id}/determinism"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/replay.py",
                "mcoi/mcoi_runtime/core/replay_determinism_harness.py",
                "mcoi/tests/test_replay_determinism_endpoints.py",
                "mcoi/tests/test_replay_determinism_harness.py",
                "docs/03_trace_and_replay.md",
            ],
            "Replay determinism route emits governed reports over completed traces with bounded operation specs.",
        ),
        _surface(
            "tool_invocation",
            ["/api/v1/tools/invoke", "/api/v1/workflow/tools"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data.py",
                "mcoi/mcoi_runtime/app/routers/workflow.py",
                "mcoi/mcoi_runtime/core/tool_use.py",
                "mcoi/mcoi_runtime/mcp/capability_bridge.py",
                "gateway/mcp_operator_read_model.py",
                "gateway/mcp_capability_fabric.py",
                "gateway/mcp_capabilities.py",
                "scripts/validate_mcp_capability_manifest.py",
                "scripts/validate_mcp_operator_checklist.py",
                "examples/mcp_capability_manifest.json",
                "examples/mcp_operator_handoff_checklist.json",
                "docs/55_mcp_capability_manifest.md",
                "tests/test_gateway/test_mcp_capability_fabric.py",
                "tests/test_validate_mcp_capability_manifest.py",
                "tests/test_validate_mcp_operator_checklist.py",
            ],
            "Tool invocation and MCP capability import bind action proof ids, capability policy receipts, authority-obligation ownership records, validated operator manifests, and machine-readable handoff checklists.",
        ),
        _surface(
            "governed_session",
            ["GovernedSession.llm", "GovernedSession.execute", "GovernedSession.query"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/core/governed_session.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
                "mcoi/tests/test_governed_session.py",
            ],
            "Session entry points return request-envelope proofs and retain action proof lineage.",
        ),
        _surface(
            "health_docs_exempt",
            ["/health", "/docs", "/openapi.json", "/redoc"],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            ["gateway/server.py"],
            "Operational liveness and documentation surfaces are outside the proof-critical path.",
        ),
        _surface(
            "lineage_query_api",
            [
                "/api/v1/lineage/resolve",
                "/api/v1/lineage/{trace_id}",
                "/api/v1/lineage/output/{output_id}",
                "/api/v1/lineage/command/{command_id}",
            ],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/lineage.py",
                "mcoi/mcoi_runtime/core/lineage_query.py",
                "docs/42_lineage_query_api.md",
                "schemas/lineage_query.schema.json",
                "schemas/trace_entry.schema.json",
                "schemas/replay_record.schema.json",
            ],
            "Lineage query API resolves read-only lineage:// URIs with bounded output, command, graph, and policy-version read models.",
        ),
    ]
    closure_actions = [
        {
            "action_id": "bind_tool_arguments_to_capability_policy_receipts",
            "surfaces": ["tool_invocation", "gateway_capability_fabric"],
            "status": "closed",
        },
        {
            "action_id": "bind_mcp_capabilities_to_authority_obligation_records",
            "surfaces": ["tool_invocation", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "publish_validated_mcp_capability_manifest_contract",
            "surfaces": ["tool_invocation", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "normalize_gateway_request_receipt_envelopes",
            "surfaces": ["gateway_capability_fabric"],
            "status": "closed",
        },
        {
            "action_id": "bound_authority_read_models_to_paginated_windows",
            "surfaces": ["gateway_approval_resolution", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "classify_authority_operator_controls",
            "surfaces": ["authority_operator_controls", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "implement_lineage_query_routes_and_schema",
            "surfaces": ["lineage_query_api"],
            "status": "closed",
        },
        {
            "action_id": "connect_pilot_scaffold_to_hosted_provisioning_endpoint",
            "surfaces": ["pilot_provisioning"],
            "status": "closed",
        },
        {
            "action_id": "publish_hosted_demo_sandbox_read_models",
            "surfaces": ["hosted_demo_sandbox"],
            "status": "closed",
        },
        {
            "action_id": "publish_federated_control_plane_read_model",
            "surfaces": ["federated_control_plane"],
            "status": "closed",
        },
        {
            "action_id": "classify_finance_approval_packet_routes",
            "surfaces": ["finance_approval_packets"],
            "status": "closed",
        },
        {
            "action_id": "classify_data_governance_routes",
            "surfaces": ["data_governance_controls"],
            "status": "closed",
        },
        {
            "action_id": "classify_compliance_evidence_exports",
            "surfaces": ["compliance_evidence_exports"],
            "status": "closed",
        },
        {
            "action_id": "classify_audit_chain_api",
            "surfaces": ["audit_chain_api"],
            "status": "closed",
        },
        {
            "action_id": "classify_runbook_learning_routes",
            "surfaces": ["runbook_learning_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "publish_runtime_conformance_attestation",
            "surfaces": ["runtime_conformance_attestation"],
            "status": "closed",
        },
        {
            "action_id": "publish_production_evidence_plane",
            "surfaces": ["production_evidence_plane", "gateway_runtime_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_capability_plan_evidence_bundles",
            "surfaces": ["capability_plan_evidence_bundle", "runtime_conformance_attestation"],
            "status": "closed",
        },
        {
            "action_id": "publish_deployment_orchestration_receipt_contract",
            "surfaces": ["gateway_runtime_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_runtime_reflex_engine_read_models",
            "surfaces": ["runtime_reflex_engine", "runtime_conformance_attestation"],
            "status": "closed",
        },
        {
            "action_id": "publish_governed_operational_intelligence_witnesses",
            "surfaces": ["governed_operational_intelligence"],
            "status": "closed",
        },
        {
            "action_id": "publish_capability_forge_candidate_contract",
            "surfaces": ["capability_forge"],
            "status": "closed",
        },
        {
            "action_id": "publish_capability_maturity_assessment_contract",
            "surfaces": ["capability_maturity_assessment"],
            "status": "closed",
        },
        {
            "action_id": "publish_networked_worker_mesh_contract",
            "surfaces": ["networked_worker_mesh"],
            "status": "closed",
        },
        {
            "action_id": "publish_agent_identity_contract",
            "surfaces": ["agent_identity"],
            "status": "closed",
        },
        {
            "action_id": "publish_claim_verification_report_contract",
            "surfaces": ["claim_verification"],
            "status": "closed",
        },
        {
            "action_id": "publish_connector_self_healing_receipt_contract",
            "surfaces": ["connector_self_healing"],
            "status": "closed",
        },
        {
            "action_id": "publish_collaboration_case_contract",
            "surfaces": ["collaboration_cases"],
            "status": "closed",
        },
        {
            "action_id": "publish_capability_maturity_contract",
            "surfaces": ["capability_maturity"],
            "status": "closed",
        },
        {
            "action_id": "publish_policy_prover_counterexample_contract",
            "surfaces": ["policy_prover"],
            "status": "closed",
        },
        {
            "action_id": "publish_memory_lattice_admission_contract",
            "surfaces": ["memory_lattice"],
            "status": "closed",
        },
        {
            "action_id": "publish_workflow_mining_draft_contract",
            "surfaces": ["workflow_mining"],
            "status": "closed",
        },
        {
            "action_id": "publish_domain_operating_pack_contract",
            "surfaces": ["domain_operating_pack"],
            "status": "closed",
        },
        {
            "action_id": "publish_multimodal_operation_receipt_contract",
            "surfaces": ["multimodal_operating_layer"],
            "status": "closed",
        },
        {
            "action_id": "publish_physical_action_receipt_contract",
            "surfaces": ["physical_action_boundary"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_operation_receipt_contract",
            "surfaces": ["temporal_kernel"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_evidence_freshness_receipt_contract",
            "surfaces": ["temporal_evidence_freshness"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_memory_receipt_contract",
            "surfaces": ["temporal_memory"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_memory_refresh_receipt_contract",
            "surfaces": ["temporal_memory_refresh"],
            "status": "closed",
        },
        {
            "action_id": "classify_temporal_scheduler_routes",
            "surfaces": ["temporal_kernel"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_scheduler_receipt_contract",
            "surfaces": ["temporal_scheduler"],
            "status": "closed",
        },
        {
            "action_id": "publish_policy_proof_report_contract",
            "surfaces": ["policy_proof_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_capability_upgrade_plan_contract",
            "surfaces": ["autonomous_capability_upgrade"],
            "status": "closed",
        },
        {
            "action_id": "publish_autonomous_test_generation_plan_contract",
            "surfaces": ["autonomous_test_generation"],
            "status": "closed",
        },
        {
            "action_id": "publish_trust_ledger_bundle_contract",
            "surfaces": ["trust_ledger"],
            "status": "closed",
        },
        {
            "action_id": "publish_trust_ledger_anchor_receipt_contract",
            "surfaces": ["trust_ledger"],
            "status": "closed",
        },
    ]
    return {
        "schema_version": 1,
        "generated_by": "scripts/proof_coverage_matrix.py",
        "coverage_levels": COVERAGE_LEVELS,
        "coverage_states": COVERAGE_STATES,
        "coverage_summary": coverage_summary(surfaces),
        "surfaces": surfaces,
        "route_coverage": route_coverage_report(surfaces, discover_declared_routes()),
        "closure_actions": closure_actions,
    }


def coverage_summary(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic aggregate proof coverage counts."""
    by_state = {state: 0 for state in COVERAGE_STATES}
    by_request_proof = {level: 0 for level in COVERAGE_LEVELS}
    by_action_proof = {level: 0 for level in COVERAGE_LEVELS}
    by_audit = {level: 0 for level in COVERAGE_LEVELS}
    for surface in surfaces:
        by_state[surface["coverage_state"]] = by_state.get(surface["coverage_state"], 0) + 1
        by_request_proof[surface["request_proof"]] = by_request_proof.get(surface["request_proof"], 0) + 1
        by_action_proof[surface["action_proof"]] = by_action_proof.get(surface["action_proof"], 0) + 1
        by_audit[surface["audit"]] = by_audit.get(surface["audit"], 0) + 1
    return {
        "surface_count": len(surfaces),
        "by_coverage_state": by_state,
        "by_request_proof": by_request_proof,
        "by_action_proof": by_action_proof,
        "by_audit": by_audit,
    }


def discover_declared_routes(repo_root: Path = REPO_ROOT) -> set[str]:
    route_roots = [repo_root / "mcoi" / "mcoi_runtime" / "app" / "routers", repo_root / "gateway"]
    routes = set(FRAMEWORK_GENERATED_ROUTES)
    for route_root in route_roots:
        if not route_root.exists():
            continue
        for python_file in route_root.rglob("*.py"):
            if "__pycache__" in python_file.parts:
                continue
            source = python_file.read_text(encoding="utf-8")
            file_routes = ROUTE_PATTERN.findall(source)
            routes.update(file_routes)
            prefixes = ROUTER_PREFIX_PATTERN.findall(source)
            for prefix in prefixes:
                routes.update(f"{prefix}{route}" for route in file_routes if route.startswith("/"))
    return routes


def route_coverage_report(
    surfaces: list[dict[str, Any]],
    routes: set[str],
) -> dict[str, Any]:
    """Return per-route coverage classification for declared callable routes."""
    route_records = []
    for route in sorted(_proof_relevant_routes(routes)):
        surface = _surface_for_route(route, surfaces)
        if surface is None:
            route_records.append(
                {
                    "route": route,
                    "surface_id": "unclassified_declared_route",
                    "coverage_state": "unproven",
                }
            )
            continue
        route_records.append(
            {
                "route": route,
                "surface_id": surface["surface_id"],
                "coverage_state": surface["coverage_state"],
            }
        )
    by_state = {state: 0 for state in COVERAGE_STATES}
    for record in route_records:
        by_state[record["coverage_state"]] += 1
    return {
        "route_count": len(route_records),
        "by_coverage_state": by_state,
        "unclassified_route_count": by_state["unproven"],
        "routes": route_records,
    }


def _proof_relevant_routes(routes: set[str]) -> tuple[str, ...]:
    """Return routes that require an explicit proof coverage classification."""
    prefixes = (
        "/api/v1",
        "/webhook",
        "/authority",
        "/runtime",
        "/gateway",
        "/anchors",
        "/capability",
        "/commands",
        "/evidence",
    )
    return tuple(route for route in routes if route.startswith(prefixes))


def _surface_for_route(route: str, surfaces: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the surface that explicitly covers a declared route."""
    for surface in surfaces:
        for path in surface["representative_paths"]:
            if not path.startswith("/"):
                continue
            if path == route:
                return surface
    for surface in surfaces:
        for path in surface["representative_paths"]:
            if path.startswith("/") and path.endswith("*") and route.startswith(path[:-1]):
                return surface
    return None


def validate_matrix_routes(matrix: dict[str, Any], routes: set[str]) -> list[str]:
    missing: list[str] = []
    for surface in matrix["surfaces"]:
        if surface.get("coverage_state") == "unproven":
            continue
        for path in surface["representative_paths"]:
            if not path.startswith("/"):
                continue
            if path.endswith("*"):
                if not any(route.startswith(path[:-1]) for route in routes):
                    missing.append(path)
                continue
            if path not in routes:
                missing.append(path)
    return missing


def write_matrix(path: Path, matrix: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or validate the proof coverage matrix.")
    parser.add_argument("--output", type=Path, default=CANONICAL_OUTPUT)
    parser.add_argument("--assurance-output", type=Path, default=ASSURANCE_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = proof_coverage_matrix()
    missing_routes = validate_matrix_routes(matrix, discover_declared_routes())
    if missing_routes:
        raise SystemExit(f"Representative routes are not declared: {', '.join(sorted(missing_routes))}")
    if args.check:
        expected = json.dumps(matrix, indent=2, sort_keys=True) + "\n"
        actual = args.output.read_text(encoding="utf-8")
        if actual != expected:
            raise SystemExit(f"{args.output} is stale; run scripts/proof_coverage_matrix.py")
        return 0
    write_matrix(args.output, matrix)
    write_matrix(args.assurance_output, matrix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
