"""Purpose: generate the proof coverage matrix witness.

Governance scope: records request-proof, action-proof, runtime-witness, and
audit-chain coverage for externally callable control-plane surfaces.
Dependencies: repository source tree, route decorators, JSON serialization.
Invariants: generated output is deterministic; representative HTTP routes map
to declared application routes or explicit wildcard families.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"
DOC_OUTPUT = REPO_ROOT / "docs" / "40_proof_coverage_matrix.md"
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
    runtime_witness_anchor_aliases: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    surface = {
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
    if runtime_witness_anchor_aliases:
        surface["runtime_witness_anchor_aliases"] = {
            witness: list(aliases)
            for witness, aliases in runtime_witness_anchor_aliases.items()
        }
    return surface


def proof_coverage_matrix() -> dict[str, Any]:
    gateway_witnesses = [
        "command_lifecycle_events_are_hash_linked",
        "terminal_closure_requires_evidence_refs",
        "terminal_closure_exposes_whqr_replay_ref",
        "successful_response_is_bound_to_response_evidence_closure",
        "command_interpretation_receipt_read_model_bounds_raw_message",
        "command_interpretation_receipt_read_model_schema_valid",
        "command_interpretation_receipt_requires_operator_authority",
        "command_interpretation_receipt_replays_from_command_store",
        "universal_action_proof_replays_from_command_events",
        "universal_action_proof_exposes_whqr_replay_ref",
        "universal_action_runtime_record_exports_contract_shape",
        "universal_action_orchestration_replays_from_command_events",
        "universal_action_orchestration_exposes_whqr_replay_ref",
        "operator_universal_action_read_model_filters_command_proofs",
        "operator_universal_action_read_model_exposes_whqr_replay_ref",
        "operator_universal_action_console_renders_replay_state",
        "operator_receipt_viewer_groups_bounded_receipts",
        "operator_receipt_viewer_schema_valid",
        "operator_current_task_read_model_classifies_states",
        "operator_receipt_and_current_task_consoles_render_bounded_tables",
        "operator_receipt_viewer_requires_operator_authority",
    ]
    surfaces = [
        _surface(
            "gateway_capability_fabric",
            [
                "/webhook/*",
                "/capability-fabric/read-model",
                "/capability-fabric/admission-audits",
                "/capability-fabric/capsule-admissions",
                "/capability-fabric/capsule-admission-receipts",
                "/commands/{command_id}/closure",
                "/commands/{command_id}/capability-admission",
                "/commands/{command_id}/universal-action-proof",
                "/commands/{command_id}/universal-action-orchestration",
                "/commands/{command_id}/interpretation-receipt",
                "/operator/universal-actions/read-model",
                "/operator/universal-actions",
                "/operator/receipts/read-model",
                "/operator/receipts",
                "/operator/current-task/read-model",
                "/operator/current-task",
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
                "gateway/command_spine.py",
                "mcoi/mcoi_runtime/app/governed_execution.py",
                "mcoi/mcoi_runtime/core/command_capability_admission.py",
                "mcoi/mcoi_runtime/core/domain_capsule_compiler.py",
                "mcoi/mcoi_runtime/core/universal_action_kernel.py",
                "schemas/command_interpretation_receipt_read_model.schema.json",
                "schemas/operator_receipt_viewer_read_model.schema.json",
                "schemas/current_task_read_model.schema.json",
                "gateway/operator_receipt_viewer.py",
                "mcoi/tests/test_universal_action_kernel.py",
                "tests/test_gateway/test_capability_capsule_installer.py",
                "tests/test_gateway/test_webhooks.py",
                "tests/test_governed_capability_fabric.py",
            ],
            "Gateway command admission, request receipt envelopes, bounded interpretation-receipt and operator receipt/task read models, terminal closure with WHQR replay refs, universal action proof replay, orchestration, and operator replay with WHQR replay refs, capsule compiler certification-evidence manifests, and the capsule admission installer receipt expose runtime witnesses.",
            [
                *gateway_witnesses,
                "capability_admission_audits_filter_status",
                "command_capability_admission_read_model_reports_accepted_witness",
                "capsule_compiler_emits_certification_evidence_manifest",
                "capsule_installer_stamps_admission_receipt",
                "capsule_admission_operator_endpoint_lists_receipt",
                "invalid_capsule_admission_preserves_registry_state",
                "physical_capsule_admission_runs_promotion_preflight",
            ],
            runtime_witness_anchor_aliases={
                "command_lifecycle_events_are_hash_linked": ["command_closure_read_model"],
                "terminal_closure_requires_evidence_refs": ["command_closure_read_model"],
                "terminal_closure_exposes_whqr_replay_ref": ["command_closure_read_model"],
                "successful_response_is_bound_to_response_evidence_closure": ["command_closure_read_model"],
                "command_interpretation_receipt_read_model_bounds_raw_message": [
                    "command_interpretation_receipt_read_model_bounds_raw_message",
                ],
                "command_interpretation_receipt_read_model_schema_valid": [
                    "command_interpretation_receipt_read_model_bounds_raw_message",
                ],
                "command_interpretation_receipt_requires_operator_authority": [
                    "command_interpretation_receipt_requires_operator_authority_in_production",
                ],
                "command_interpretation_receipt_replays_from_command_store": [
                    "command_interpretation_receipt_read_model_replays_from_command_store",
                ],
                "universal_action_proof_replays_from_command_events": [
                    "command_universal_action_proof_read_model",
                ],
                "universal_action_proof_exposes_whqr_replay_ref": [
                    "command_universal_action_proof_read_model",
                ],
                "universal_action_runtime_record_exports_contract_shape": [
                    "universal_action_result_exports_valid_allowed_uao_record",
                    "universal_action_result_exports_valid_blocked_uao_record",
                ],
                "universal_action_orchestration_replays_from_command_events": [
                    "universal_command_orchestration_record_replays_success_events",
                    "universal_command_orchestration_record_replays_blocked_events",
                    "command_universal_action_orchestration_read_model",
                ],
                "universal_action_orchestration_exposes_whqr_replay_ref": [
                    "command_universal_action_orchestration_read_model",
                ],
                "operator_universal_action_read_model_filters_command_proofs": [
                    "operator_universal_actions_read_model_filters_proofs",
                ],
                "operator_universal_action_read_model_exposes_whqr_replay_ref": [
                    "operator_universal_actions_read_model_filters_proofs",
                ],
                "operator_universal_action_console_renders_replay_state": [
                    "operator_universal_actions_console_renders_proof_table",
                ],
                "operator_receipt_viewer_groups_bounded_receipts": [
                    "operator_receipt_viewer_read_model_groups_bounded_receipts",
                ],
                "operator_receipt_viewer_schema_valid": [
                    "operator_receipt_viewer_read_model_groups_bounded_receipts",
                ],
                "operator_current_task_read_model_classifies_states": [
                    "operator_current_task_read_model_classifies_waiting_blocked_and_completed",
                ],
                "operator_receipt_and_current_task_consoles_render_bounded_tables": [
                    "operator_receipt_and_current_task_consoles_render_bounded_tables",
                ],
                "operator_receipt_viewer_requires_operator_authority": [
                    "operator_receipt_viewer_requires_operator_authority_in_production",
                ],
                "capability_admission_audits_filter_status": [
                    "fabric_admission_blocks_uninstalled_runtime_intent",
                ],
                "capsule_compiler_emits_certification_evidence_manifest": [
                    "domain_capsule_compiler_emits_certification_evidence_manifest",
                ],
                "capsule_installer_stamps_admission_receipt": [
                    "capsule_installer_admits_certified_handoff_batch_with_receipt",
                ],
                "capsule_admission_operator_endpoint_lists_receipt": [
                    "capsule_admission_operator_endpoint_installs_and_lists_receipt",
                ],
                "invalid_capsule_admission_preserves_registry_state": [
                    "capsule_installer_returns_rejected_receipt_without_registry_mutation",
                    "capsule_admission_operator_endpoint_rejects_invalid_payload",
                ],
                "physical_capsule_admission_runs_promotion_preflight": [
                    "capsule_installer_runs_physical_preflight_before_registry_mutation",
                ],
            },
        ),
        _surface(
            "local_assurance_refresh",
            [
                "refresh_local_assurance.run_refresh",
                "refresh_local_assurance.LOCAL_ASSURANCE_STEPS",
                "run_workspace_governance_checks.local_assurance_plan",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "scripts/refresh_local_assurance.py",
                "scripts/run_workspace_governance_checks.py",
                "tests/test_refresh_local_assurance.py",
                "tests/test_run_workspace_governance_checks.py",
            ],
            "Local assurance refresh regenerates deterministic no-secret evidence receipts, including blocked durable Gmail OAuth handoff, TeamOps shared inbox handoff, read-only probe-authority, and live-probe operator-input receipts, exposes dry-run command receipts, and remains part of the workspace governance preflight plan.",
            [
                "local_assurance_refresh_includes_durable_gmail_receipts",
                "local_assurance_refresh_includes_team_ops_receipts",
                "local_assurance_dry_run_does_not_execute",
                "local_assurance_stops_on_first_failure",
                "workspace_preflight_includes_local_assurance_plan",
            ],
            runtime_witness_anchor_aliases={
                "local_assurance_refresh_includes_durable_gmail_receipts": [
                    "default_refresh_steps_cover_local_assurance_surfaces",
                ],
                "local_assurance_refresh_includes_team_ops_receipts": [
                    "default_refresh_steps_cover_local_assurance_surfaces",
                ],
                "local_assurance_dry_run_does_not_execute": [
                    "dry_run_returns_step_receipts_without_invoking_runner",
                ],
                "local_assurance_stops_on_first_failure": [
                    "runner_injection_stops_on_first_failure",
                ],
                "workspace_preflight_includes_local_assurance_plan": [
                    "build_check_commands_are_ordered_and_repo_local",
                ],
            },
        ),
        _surface(
            "agentic_service_harness_status_read_model",
            ["/api/v1/harness/status"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/server.py",
                "gateway/agentic_service_harness_status.py",
                "gateway/agentic_service_harness_read_model_producer.py",
                "scripts/validate_agentic_service_harness_read_only_status_route.py",
                "scripts/validate_agentic_service_harness_read_only_status_route_design.py",
                "tests/test_gateway/test_agentic_service_harness_status_route.py",
                "tests/test_validate_agentic_service_harness_read_only_status_route.py",
                "tests/test_validate_agentic_service_harness_read_only_status_route_design.py",
            ],
            (
                "Agentic service harness status exposes one bounded read-only route, "
                "rejects mutation methods, projects only status/read-model evidence, "
                "and grants no live producer, adapter, secret, deployment, or branch authority."
            ),
            [
                "harness_status_projection_accepts_default_fixture",
                "harness_status_gateway_route_is_read_only",
                "harness_status_gateway_route_reads_runtime_source",
                "read_only_status_route_accepts_default_implementation",
                "read_only_status_route_design_accepts_default_artifact",
            ],
        ),
        _surface(
            "component_harness_read_model",
            ["/api/v1/components/read-model"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_read_model.py",
                "mcoi/mcoi_runtime/app/routers/components.py",
                "schemas/component_read_model.schema.json",
                "examples/component_read_model.foundation.json",
                "scripts/validate_component_read_model.py",
                "mcoi/tests/test_component_read_model_route.py",
                "tests/test_validate_component_read_model.py",
            ],
            "Component Harness read model joins registry, router inventory, and proof binding into one bounded projection with live execution, connector send, mutation, and terminal closure authority denied.",
            [
                "component_read_model_builds_registry_router_proof_projection",
                "component_read_model_route_is_read_only",
                "component_read_model_schema_valid",
                "component_read_model_blocks_live_authority",
                "component_read_model_example_matches_runtime_projection",
            ],
            runtime_witness_anchor_aliases={
                "component_read_model_builds_registry_router_proof_projection": [
                    "component_read_model_builds_registry_router_proof_projection",
                ],
                "component_read_model_route_is_read_only": [
                    "component_read_model_route_is_read_only",
                ],
                "component_read_model_schema_valid": [
                    "component_read_model_schema_valid",
                ],
                "component_read_model_blocks_live_authority": [
                    "component_read_model_blocks_live_authority",
                ],
                "component_read_model_example_matches_runtime_projection": [
                    "component_read_model_example_matches_runtime_projection",
                ],
            },
        ),
        _surface(
            "universal_symbol_operator_read_models",
            [
                "/api/v1/components/symbols",
                "software_receipt_symbols",
                "build_worker_receipt_symbol_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol.schema.json",
                "mcoi/mcoi_runtime/core/symbol_skill_adapter.py",
                "mcoi/mcoi_runtime/app/symbol_operator_read_models.py",
                "mcoi/mcoi_runtime/app/software_receipt_observability.py",
                "mcoi/mcoi_runtime/app/routers/components.py",
                "mcoi/tests/test_symbol_operator_read_models.py",
                "mcoi/tests/test_symbol_skill_adapter.py",
                "mcoi/tests/test_software_receipt_observability.py",
                "tests/test_validate_universal_symbol_kernel.py",
            ],
            "UniversalSymbol operator read models project component registry entries, software receipts, and worker receipt chains into schema-valid symbol envelopes while denying connector calls, runtime dispatch, filesystem writes, state mutation, terminal closure, success claims, and raw payload retention.",
            [
                "component_symbol_read_model_projects_schema_valid_symbols",
                "component_symbol_route_is_read_only",
                "worker_receipt_symbol_read_model_projects_schema_valid_symbols",
                "symbol_operator_read_models_deny_runtime_authority",
                "symbol_operator_read_model_rejects_invalid_limits",
                "worker_receipt_symbol_read_model_rejects_live_fixture_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_symbol_read_model_projects_schema_valid_symbols": [
                    "component_symbol_read_model_projects_schema_valid_symbols"
                ],
                "component_symbol_route_is_read_only": [
                    "component_symbol_route_is_read_only"
                ],
                "worker_receipt_symbol_read_model_projects_schema_valid_symbols": [
                    "worker_receipt_symbol_read_model_projects_schema_valid_symbols"
                ],
                "symbol_operator_read_models_deny_runtime_authority": [
                    "symbol_operator_read_models_deny_runtime_authority"
                ],
                "symbol_operator_read_model_rejects_invalid_limits": [
                    "symbol_operator_read_model_rejects_invalid_limits"
                ],
                "worker_receipt_symbol_read_model_rejects_live_fixture_drift": [
                    "worker_receipt_symbol_read_model_rejects_live_fixture_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_runtime_admission_policy",
            [
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "validate_universal_symbol_runtime_admission_policy",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "mcoi/mcoi_runtime/core/symbol_skill_adapter.py",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_admission_policy.py",
                "tests/test_validate_universal_symbol_kernel.py",
            ],
            "UniversalSymbol runtime admission policy defines blocked skill-by-skill admission gates while denying runtime registration, live dispatch, connector calls, filesystem writes, state mutation, receipt-store append, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_runtime_admission_policy_validates",
                "runtime_admission_policy_rejects_live_dispatch_drift",
                "runtime_admission_policy_rejects_receipt_append_drift",
                "runtime_admission_policy_rejects_skill_admission_upgrade",
                "runtime_admission_policy_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_runtime_admission_policy_validates": [
                    "foundation_universal_symbol_runtime_admission_policy_validates"
                ],
                "runtime_admission_policy_rejects_live_dispatch_drift": [
                    "runtime_admission_policy_rejects_live_dispatch_drift"
                ],
                "runtime_admission_policy_rejects_receipt_append_drift": [
                    "runtime_admission_policy_rejects_receipt_append_drift"
                ],
                "runtime_admission_policy_rejects_skill_admission_upgrade": [
                    "runtime_admission_policy_rejects_skill_admission_upgrade"
                ],
                "runtime_admission_policy_rejects_evidence_ref_count_drift": [
                    "runtime_admission_policy_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_runtime_admission_evidence_receipt",
            [
                "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
                "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
                "validate_universal_symbol_runtime_admission_evidence_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
                "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_authority_read_model.schema.json",
                "examples/universal_symbol_runtime_authority_read_model.foundation.json",
                "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
                "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py",
                "scripts/validate_universal_symbol_runtime_admission_policy.py",
                "scripts/validate_universal_symbol_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_authority_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol runtime admission evidence receipt records missing live runtime, operator, orchestration, receipt-store, skill-lane, rollback, and proof evidence while denying runtime admission, registration, dispatch, connector calls, receipt-store append, mutation, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_runtime_admission_evidence_receipt_validates",
                "runtime_admission_evidence_receipt_rejects_authority_drift",
                "runtime_admission_evidence_receipt_rejects_missing_live_evidence_kind",
                "runtime_admission_evidence_receipt_rejects_missing_delta_reject",
                "runtime_admission_evidence_receipt_rejects_consistency_drift",
                "runtime_admission_evidence_receipt_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_runtime_admission_evidence_receipt_validates": [
                    "foundation_universal_symbol_runtime_admission_evidence_receipt_validates"
                ],
                "runtime_admission_evidence_receipt_rejects_authority_drift": [
                    "runtime_admission_evidence_receipt_rejects_authority_drift"
                ],
                "runtime_admission_evidence_receipt_rejects_missing_live_evidence_kind": [
                    "runtime_admission_evidence_receipt_rejects_missing_live_evidence_kind"
                ],
                "runtime_admission_evidence_receipt_rejects_missing_delta_reject": [
                    "runtime_admission_evidence_receipt_rejects_missing_delta_reject"
                ],
                "runtime_admission_evidence_receipt_rejects_consistency_drift": [
                    "runtime_admission_evidence_receipt_rejects_consistency_drift"
                ],
                "runtime_admission_evidence_receipt_rejects_evidence_ref_count_drift": [
                    "runtime_admission_evidence_receipt_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_runtime_live_witness_input_receipt",
            [
                "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
                "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
                "validate_universal_symbol_runtime_live_witness_input_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
                "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
                "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
                "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_runtime_authority_read_model.schema.json",
                "examples/universal_symbol_runtime_authority_read_model.foundation.json",
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/produce_universal_symbol_runtime_live_witness_input_receipt.py",
                "scripts/validate_universal_symbol_runtime_live_witness_input_receipt.py",
                "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py",
                "scripts/validate_universal_symbol_runtime_authority_read_model.py",
                "tests/test_produce_universal_symbol_runtime_live_witness_input_receipt.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol runtime live witness input receipt names endpoint, process, probe, no-effect dry-run, receipt-store denial, operator observation, freshness, and proof coverage inputs while denying live witness acceptance, runtime admission, dispatch, connector calls, receipt-store append, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_runtime_live_witness_input_receipt_validates",
                "runtime_live_witness_input_receipt_rejects_authority_drift",
                "runtime_live_witness_input_receipt_rejects_missing_input_kind",
                "runtime_live_witness_input_receipt_rejects_missing_delta_reject",
                "runtime_live_witness_input_receipt_rejects_consistency_drift",
                "runtime_live_witness_input_receipt_rejects_evidence_ref_count_drift",
                "producer_builds_foundation_receipt_without_authority",
                "producer_accepts_reference_overrides_without_accepting_live_witness",
                "producer_rejects_empty_or_unknown_input_refs",
                "cli_stdout_receipt_validates_without_writing",
                "cli_output_write_reports_bounded_summary",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_runtime_live_witness_input_receipt_validates": [
                    "foundation_universal_symbol_runtime_live_witness_input_receipt_validates"
                ],
                "runtime_live_witness_input_receipt_rejects_authority_drift": [
                    "runtime_live_witness_input_receipt_rejects_authority_drift"
                ],
                "runtime_live_witness_input_receipt_rejects_missing_input_kind": [
                    "runtime_live_witness_input_receipt_rejects_missing_input_kind"
                ],
                "runtime_live_witness_input_receipt_rejects_missing_delta_reject": [
                    "runtime_live_witness_input_receipt_rejects_missing_delta_reject"
                ],
                "runtime_live_witness_input_receipt_rejects_consistency_drift": [
                    "runtime_live_witness_input_receipt_rejects_consistency_drift"
                ],
                "runtime_live_witness_input_receipt_rejects_evidence_ref_count_drift": [
                    "runtime_live_witness_input_receipt_rejects_evidence_ref_count_drift"
                ],
                "producer_builds_foundation_receipt_without_authority": [
                    "producer_builds_foundation_receipt_without_authority"
                ],
                "producer_accepts_reference_overrides_without_accepting_live_witness": [
                    "producer_accepts_reference_overrides_without_accepting_live_witness"
                ],
                "producer_rejects_empty_or_unknown_input_refs": [
                    "producer_rejects_empty_or_unknown_input_refs"
                ],
                "cli_stdout_receipt_validates_without_writing": [
                    "cli_stdout_receipt_validates_without_writing"
                ],
                "cli_output_write_reports_bounded_summary": [
                    "cli_output_write_reports_bounded_summary"
                ],
            },
        ),
        _surface(
            "repository_observation_evidence_packet",
            [
                "schemas/repository_observation_evidence_packet.schema.json",
                "examples/repository_observation_evidence_packet.foundation.json",
                "validate_repository_observation_evidence_packet",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/repository_observation_evidence_packet.schema.json",
                "examples/repository_observation_evidence_packet.foundation.json",
                "docs/94_observation_evidence_acquisition_architecture.md",
                "docs/95_repository_observation_evidence_packet_contract.md",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "scripts/produce_repository_observation_evidence_packet.py",
                "scripts/validate_repository_observation_evidence_packet.py",
                "tests/test_validate_repository_observation_evidence_packet.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "RepositoryObservationEvidencePacket records digest-only Foundation Mode and live local read-only repository observation evidence while denying raw output retention, file-content payload serialization, secret reads, source filesystem mutation, connector calls, runtime dispatch, terminal closure, success claims, and hard-constraint planning unless live proof state is Pass.",
            [
                "repository_observation_evidence_packet_passes",
                "repository_observation_rejects_authority_drift",
                "repository_observation_rejects_privacy_and_digest_drift",
                "repository_observation_rejects_hard_constraint_promotion",
                "repository_observation_rejects_receipt_ref_and_count_drift",
                "repository_observation_cli_json_accepts_relative_paths",
                "malformed_repository_observation_packet_reports_errors",
                "live_repository_observation_producer_writes_digest_only_packet",
                "live_repository_observation_command_failure_blocks_hard_planning",
                "live_repository_observation_command_allowlist_is_closed",
                "live_repository_observation_output_must_stay_workspace_local",
            ],
            runtime_witness_anchor_aliases={
                "repository_observation_evidence_packet_passes": [
                    "repository_observation_evidence_packet_passes"
                ],
                "repository_observation_rejects_authority_drift": [
                    "repository_observation_rejects_authority_drift"
                ],
                "repository_observation_rejects_privacy_and_digest_drift": [
                    "repository_observation_rejects_privacy_and_digest_drift"
                ],
                "repository_observation_rejects_hard_constraint_promotion": [
                    "repository_observation_rejects_hard_constraint_promotion"
                ],
                "repository_observation_rejects_receipt_ref_and_count_drift": [
                    "repository_observation_rejects_receipt_ref_and_count_drift"
                ],
                "repository_observation_cli_json_accepts_relative_paths": [
                    "repository_observation_cli_json_accepts_relative_paths"
                ],
                "malformed_repository_observation_packet_reports_errors": [
                    "malformed_repository_observation_packet_reports_errors"
                ],
                "live_repository_observation_producer_writes_digest_only_packet": [
                    "live_repository_observation_producer_writes_digest_only_packet"
                ],
                "live_repository_observation_command_failure_blocks_hard_planning": [
                    "live_repository_observation_command_failure_blocks_hard_planning"
                ],
                "live_repository_observation_command_allowlist_is_closed": [
                    "live_repository_observation_command_allowlist_is_closed"
                ],
                "live_repository_observation_output_must_stay_workspace_local": [
                    "live_repository_observation_output_must_stay_workspace_local"
                ],
            },
        ),
        _surface(
            "universal_symbol_lane_runtime_authority_evidence_receipt",
            [
                "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
                "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
                "validate_universal_symbol_lane_runtime_authority_evidence_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
                "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
                "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
                "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
                "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
                "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
                "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_lane_runtime_authority_evidence_receipt.py",
                "scripts/validate_universal_symbol_skill_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_admission_evidence_receipt.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol lane runtime authority evidence receipt records missing operator approval, receipt-store authority, recovery, audit, live runtime witness, and blocked-action evidence for teamops-shared-inbox, software-dev, governance-core, and worker-ledger while denying lane authority, runtime admission, dispatch, connector calls, receipt-store append, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_lane_runtime_authority_evidence_receipt_validates",
                "lane_runtime_authority_evidence_receipt_rejects_authority_drift",
                "lane_runtime_authority_evidence_receipt_rejects_missing_lane",
                "lane_runtime_authority_evidence_receipt_rejects_observed_evidence_drift",
                "lane_runtime_authority_evidence_receipt_rejects_missing_delta_reject",
                "lane_runtime_authority_evidence_receipt_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_lane_runtime_authority_evidence_receipt_validates": [
                    "foundation_universal_symbol_lane_runtime_authority_evidence_receipt_validates"
                ],
                "lane_runtime_authority_evidence_receipt_rejects_authority_drift": [
                    "lane_runtime_authority_evidence_receipt_rejects_authority_drift"
                ],
                "lane_runtime_authority_evidence_receipt_rejects_missing_lane": [
                    "lane_runtime_authority_evidence_receipt_rejects_missing_lane"
                ],
                "lane_runtime_authority_evidence_receipt_rejects_observed_evidence_drift": [
                    "lane_runtime_authority_evidence_receipt_rejects_observed_evidence_drift"
                ],
                "lane_runtime_authority_evidence_receipt_rejects_missing_delta_reject": [
                    "lane_runtime_authority_evidence_receipt_rejects_missing_delta_reject"
                ],
                "lane_runtime_authority_evidence_receipt_rejects_evidence_ref_count_drift": [
                    "lane_runtime_authority_evidence_receipt_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_lane_runtime_authority_evidence_value_receipt",
            [
                "schemas/universal_symbol_lane_runtime_authority_evidence_value_receipt.schema.json",
                "examples/universal_symbol_lane_runtime_authority_evidence_value_receipt.foundation.json",
                "validate_universal_symbol_lane_runtime_authority_evidence_value_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_lane_runtime_authority_evidence_value_receipt.schema.json",
                "examples/universal_symbol_lane_runtime_authority_evidence_value_receipt.foundation.json",
                "schemas/universal_symbol_lane_runtime_authority_evidence_receipt.schema.json",
                "examples/universal_symbol_lane_runtime_authority_evidence_receipt.foundation.json",
                "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
                "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_live_witness_input_receipt.schema.json",
                "examples/universal_symbol_runtime_live_witness_input_receipt.foundation.json",
                "schemas/universal_symbol_runtime_admission_evidence_receipt.schema.json",
                "examples/universal_symbol_runtime_admission_evidence_receipt.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/produce_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
                "scripts/validate_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
                "scripts/verify_universal_symbol_lane_runtime_authority_evidence_value_refs.py",
                "tests/test_produce_universal_symbol_lane_runtime_authority_evidence_value_receipt.py",
                "tests/test_verify_universal_symbol_lane_runtime_authority_evidence_value_refs.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol lane runtime authority evidence value receipt records and structurally verifies operator-supplied reference values for lane approval, receipt-store authority, recovery, audit, live runtime witness, and blocked actions while denying lane authority, runtime admission, dispatch, connector calls, receipt-store append, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_lane_runtime_authority_evidence_value_receipt_validates",
                "lane_runtime_authority_evidence_value_receipt_rejects_authority_drift",
                "lane_runtime_authority_evidence_value_receipt_rejects_missing_value",
                "lane_runtime_authority_evidence_value_receipt_rejects_raw_secret_ref",
                "lane_runtime_authority_evidence_value_receipt_rejects_missing_delta_reject",
                "lane_runtime_authority_evidence_value_receipt_rejects_evidence_ref_count_drift",
                "lane_value_producer_builds_ref_only_blocked_receipt",
                "lane_value_producer_accepts_ref_overrides_without_authority",
                "lane_value_producer_rejects_unknown_empty_or_secret_refs",
                "lane_value_cli_stdout_receipt_validates",
                "lane_value_cli_output_write_reports_summary",
                "verifier_blocks_template_placeholder_refs",
                "verifier_accepts_complete_refs_without_authority",
                "verifier_rejects_wrong_scheme_for_evidence_kind",
                "verifier_rejects_secret_like_ref",
                "verifier_accepts_matching_local_json_ref_without_authority",
                "verifier_rejects_local_json_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_lane_runtime_authority_evidence_value_receipt_validates": [
                    "foundation_universal_symbol_lane_runtime_authority_evidence_value_receipt_validates"
                ],
                "lane_runtime_authority_evidence_value_receipt_rejects_authority_drift": [
                    "lane_runtime_authority_evidence_value_receipt_rejects_authority_drift"
                ],
                "lane_runtime_authority_evidence_value_receipt_rejects_missing_value": [
                    "lane_runtime_authority_evidence_value_receipt_rejects_missing_value"
                ],
                "lane_runtime_authority_evidence_value_receipt_rejects_raw_secret_ref": [
                    "lane_runtime_authority_evidence_value_receipt_rejects_raw_secret_ref"
                ],
                "lane_runtime_authority_evidence_value_receipt_rejects_missing_delta_reject": [
                    "lane_runtime_authority_evidence_value_receipt_rejects_missing_delta_reject"
                ],
                "lane_runtime_authority_evidence_value_receipt_rejects_evidence_ref_count_drift": [
                    "lane_runtime_authority_evidence_value_receipt_rejects_evidence_ref_count_drift"
                ],
                "lane_value_producer_builds_ref_only_blocked_receipt": [
                    "lane_value_producer_builds_ref_only_blocked_receipt"
                ],
                "lane_value_producer_accepts_ref_overrides_without_authority": [
                    "lane_value_producer_accepts_ref_overrides_without_authority"
                ],
                "lane_value_producer_rejects_unknown_empty_or_secret_refs": [
                    "lane_value_producer_rejects_unknown_empty_or_secret_refs"
                ],
                "lane_value_cli_stdout_receipt_validates": [
                    "lane_value_cli_stdout_receipt_validates"
                ],
                "lane_value_cli_output_write_reports_summary": [
                    "lane_value_cli_output_write_reports_summary"
                ],
                "verifier_blocks_template_placeholder_refs": [
                    "verifier_blocks_template_placeholder_refs"
                ],
                "verifier_accepts_complete_refs_without_authority": [
                    "verifier_accepts_complete_refs_without_authority"
                ],
                "verifier_rejects_wrong_scheme_for_evidence_kind": [
                    "verifier_rejects_wrong_scheme_for_evidence_kind"
                ],
                "verifier_rejects_secret_like_ref": [
                    "verifier_rejects_secret_like_ref"
                ],
                "verifier_accepts_matching_local_json_ref_without_authority": [
                    "verifier_accepts_matching_local_json_ref_without_authority"
                ],
                "verifier_rejects_local_json_authority_drift": [
                    "verifier_rejects_local_json_authority_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_runtime_authority_witness",
            [
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "validate_universal_symbol_runtime_authority_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
                "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_skill_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_admission_policy.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol runtime authority witness defines runtime admission, UAO, Phi_gov, life-meaning judgment, operator approval, receipt-store authority, rollback recovery, skill admission witness, proof coverage, and terminal-closure-denial requirements while denying runtime authority, runtime registration, skill admission recording, live dispatch, connector calls, filesystem writes, external writes, receipt-store append, raw payload storage, raw secret storage, state mutation, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_runtime_authority_witness_validates",
                "runtime_authority_witness_rejects_runtime_authority_drift",
                "runtime_authority_witness_rejects_missing_requirement",
                "runtime_authority_witness_rejects_missing_delta_reject",
                "runtime_authority_witness_rejects_constraint_drift",
                "runtime_authority_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_runtime_authority_witness_validates": [
                    "foundation_universal_symbol_runtime_authority_witness_validates"
                ],
                "runtime_authority_witness_rejects_runtime_authority_drift": [
                    "runtime_authority_witness_rejects_runtime_authority_drift"
                ],
                "runtime_authority_witness_rejects_missing_requirement": [
                    "runtime_authority_witness_rejects_missing_requirement"
                ],
                "runtime_authority_witness_rejects_missing_delta_reject": [
                    "runtime_authority_witness_rejects_missing_delta_reject"
                ],
                "runtime_authority_witness_rejects_constraint_drift": [
                    "runtime_authority_witness_rejects_constraint_drift"
                ],
                "runtime_authority_witness_rejects_evidence_ref_count_drift": [
                    "runtime_authority_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_runtime_authority_read_model",
            [
                "schemas/universal_symbol_runtime_authority_read_model.schema.json",
                "examples/universal_symbol_runtime_authority_read_model.foundation.json",
                "validate_universal_symbol_runtime_authority_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_runtime_authority_read_model.schema.json",
                "examples/universal_symbol_runtime_authority_read_model.foundation.json",
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_runtime_authority_read_model.py",
                "scripts/validate_universal_symbol_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_admission_policy.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol runtime authority read model projects simple operator statuses while remaining read-only and denying runtime authority, dispatch, connector calls, receipt-store append, mutation, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_runtime_authority_read_model_validates",
                "runtime_authority_read_model_rejects_activation_drift",
                "runtime_authority_read_model_rejects_status_drift",
                "runtime_authority_read_model_rejects_missing_projection_link",
                "runtime_authority_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_runtime_authority_read_model_validates": [
                    "foundation_universal_symbol_runtime_authority_read_model_validates"
                ],
                "runtime_authority_read_model_rejects_activation_drift": [
                    "runtime_authority_read_model_rejects_activation_drift"
                ],
                "runtime_authority_read_model_rejects_status_drift": [
                    "runtime_authority_read_model_rejects_status_drift"
                ],
                "runtime_authority_read_model_rejects_missing_projection_link": [
                    "runtime_authority_read_model_rejects_missing_projection_link"
                ],
                "runtime_authority_read_model_rejects_evidence_ref_count_drift": [
                    "runtime_authority_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_skill_runtime_authority_witness",
            [
                "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
                "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
                "validate_universal_symbol_skill_runtime_authority_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_skill_runtime_authority_witness.schema.json",
                "examples/universal_symbol_skill_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_authority_witness.schema.json",
                "examples/universal_symbol_runtime_authority_witness.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "examples/universal_symbol_runtime_admission_policy.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_skill_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_authority_witness.py",
                "scripts/validate_universal_symbol_runtime_admission_policy.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol skill runtime authority witness defines lane-level authority requirements for teamops-shared-inbox, software-dev, governance-core, and worker-ledger while denying skill runtime authority, runtime registration, skill admission recording, live dispatch, connector calls, filesystem writes, external writes, receipt-store append, raw payload storage, raw secret storage, state mutation, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_skill_runtime_authority_witness_validates",
                "skill_runtime_authority_witness_rejects_skill_authority_drift",
                "skill_runtime_authority_witness_rejects_missing_lane",
                "skill_runtime_authority_witness_rejects_missing_delta_reject",
                "skill_runtime_authority_witness_rejects_constraint_drift",
                "skill_runtime_authority_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_skill_runtime_authority_witness_validates": [
                    "foundation_universal_symbol_skill_runtime_authority_witness_validates"
                ],
                "skill_runtime_authority_witness_rejects_skill_authority_drift": [
                    "skill_runtime_authority_witness_rejects_skill_authority_drift"
                ],
                "skill_runtime_authority_witness_rejects_missing_lane": [
                    "skill_runtime_authority_witness_rejects_missing_lane"
                ],
                "skill_runtime_authority_witness_rejects_missing_delta_reject": [
                    "skill_runtime_authority_witness_rejects_missing_delta_reject"
                ],
                "skill_runtime_authority_witness_rejects_constraint_drift": [
                    "skill_runtime_authority_witness_rejects_constraint_drift"
                ],
                "skill_runtime_authority_witness_rejects_evidence_ref_count_drift": [
                    "skill_runtime_authority_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_adapter_receipt_persistence_policy",
            [
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
                "validate_universal_symbol_adapter_receipt_persistence_policy",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "mcoi/mcoi_runtime/core/symbol_skill_adapter.py",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_adapter_receipt_persistence_policy.py",
                "scripts/validate_universal_symbol_receipt_store_authority_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
            ],
            "UniversalSymbol adapter receipt persistence policy permits digest/ref-only candidate receipt evaluation while denying receipt-store append, raw payload storage, raw secret storage, runtime dispatch, connector calls, writes, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_adapter_receipt_persistence_policy_validates",
                "adapter_receipt_persistence_policy_rejects_append_drift",
                "adapter_receipt_persistence_policy_rejects_raw_payload_drift",
                "adapter_receipt_persistence_policy_rejects_projection_persistence_drift",
                "adapter_receipt_persistence_policy_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_adapter_receipt_persistence_policy_validates": [
                    "foundation_universal_symbol_adapter_receipt_persistence_policy_validates"
                ],
                "adapter_receipt_persistence_policy_rejects_append_drift": [
                    "adapter_receipt_persistence_policy_rejects_append_drift"
                ],
                "adapter_receipt_persistence_policy_rejects_raw_payload_drift": [
                    "adapter_receipt_persistence_policy_rejects_raw_payload_drift"
                ],
                "adapter_receipt_persistence_policy_rejects_projection_persistence_drift": [
                    "adapter_receipt_persistence_policy_rejects_projection_persistence_drift"
                ],
                "adapter_receipt_persistence_policy_rejects_evidence_ref_count_drift": [
                    "adapter_receipt_persistence_policy_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_append_audit_witness",
            [
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "validate_universal_symbol_append_audit_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_append_audit_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
            ],
            "UniversalSymbol append audit witness defines digest-ref custody, append sequence, idempotency, durability replay, rollback/recovery, UAO, and LifeMeaningJudgment requirements while denying writer registration, write-path registration, append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_append_audit_witness_validates",
                "append_audit_witness_rejects_append_authority_drift",
                "append_audit_witness_rejects_missing_delta_reject",
                "append_audit_witness_rejects_candidate_raw_payload_drift",
                "append_audit_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_append_audit_witness_validates": [
                    "foundation_universal_symbol_append_audit_witness_validates"
                ],
                "append_audit_witness_rejects_append_authority_drift": [
                    "append_audit_witness_rejects_append_authority_drift"
                ],
                "append_audit_witness_rejects_missing_delta_reject": [
                    "append_audit_witness_rejects_missing_delta_reject"
                ],
                "append_audit_witness_rejects_candidate_raw_payload_drift": [
                    "append_audit_witness_rejects_candidate_raw_payload_drift"
                ],
                "append_audit_witness_rejects_evidence_ref_count_drift": [
                    "append_audit_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_authority_witness",
            [
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "validate_universal_symbol_receipt_store_authority_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_authority_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
            ],
            "UniversalSymbol receipt-store authority witness defines future append authority requirements, including operator identity, approval decision, temporal reapproval, revocation, lifecycle evidence, lifecycle audit, and replacement decision contracts, while keeping authority ungranted and denying writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_authority_witness_validates",
                "receipt_store_authority_witness_rejects_authority_grant_drift",
                "receipt_store_authority_witness_rejects_append_precondition_drift",
                "receipt_store_authority_witness_rejects_missing_requirement",
                "receipt_store_authority_witness_rejects_missing_lifecycle_requirement",
                "receipt_store_authority_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_authority_witness_validates": [
                    "foundation_universal_symbol_receipt_store_authority_witness_validates"
                ],
                "receipt_store_authority_witness_rejects_authority_grant_drift": [
                    "receipt_store_authority_witness_rejects_authority_grant_drift"
                ],
                "receipt_store_authority_witness_rejects_append_precondition_drift": [
                    "receipt_store_authority_witness_rejects_append_precondition_drift"
                ],
                "receipt_store_authority_witness_rejects_missing_requirement": [
                    "receipt_store_authority_witness_rejects_missing_requirement"
                ],
                "receipt_store_authority_witness_rejects_missing_lifecycle_requirement": [
                    "receipt_store_authority_witness_rejects_missing_lifecycle_requirement"
                ],
                "receipt_store_authority_witness_rejects_evidence_ref_count_drift": [
                    "receipt_store_authority_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_operator_approval_witness",
            [
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "validate_universal_symbol_receipt_store_operator_approval_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_operator_approval_witness.py",
                "scripts/validate_universal_symbol_receipt_store_operator_identity_witness.py",
                "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store operator approval witness defines operator identity, explicit approval decision, approval scope, tenant scope, expiry/reapproval, revocation, audit receipt, and terminal-closure-denial requirements while binding named operator identity and approval decision witness contracts and denying approval recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_operator_approval_witness_validates",
                "operator_approval_witness_rejects_approval_authority_drift",
                "operator_approval_witness_rejects_missing_requirement",
                "operator_approval_witness_rejects_missing_delta_reject",
                "operator_approval_witness_rejects_constraint_drift",
                "operator_approval_witness_rejects_scope_constraint_drift",
                "operator_approval_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_operator_approval_witness_validates": [
                    "foundation_universal_symbol_receipt_store_operator_approval_witness_validates"
                ],
                "operator_approval_witness_rejects_approval_authority_drift": [
                    "operator_approval_witness_rejects_approval_authority_drift"
                ],
                "operator_approval_witness_rejects_missing_requirement": [
                    "operator_approval_witness_rejects_missing_requirement"
                ],
                "operator_approval_witness_rejects_missing_delta_reject": [
                    "operator_approval_witness_rejects_missing_delta_reject"
                ],
                "operator_approval_witness_rejects_constraint_drift": [
                    "operator_approval_witness_rejects_constraint_drift"
                ],
                "operator_approval_witness_rejects_scope_constraint_drift": [
                    "operator_approval_witness_rejects_scope_constraint_drift"
                ],
                "operator_approval_witness_rejects_evidence_ref_count_drift": [
                    "operator_approval_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_operator_identity_witness",
            [
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "validate_universal_symbol_receipt_store_operator_identity_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_operator_identity_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store operator identity witness defines live operator subject, trusted control studio binding, tenant scope binding, actor proof, session authentication, freshness window, revocation path, and audit receipt requirements while denying identity binding, approval recording, approval decision recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_operator_identity_witness_validates",
                "operator_identity_witness_rejects_identity_authority_drift",
                "operator_identity_witness_rejects_missing_requirement",
                "operator_identity_witness_rejects_missing_delta_reject",
                "operator_identity_witness_rejects_constraint_drift",
                "operator_identity_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_operator_identity_witness_validates": [
                    "foundation_universal_symbol_receipt_store_operator_identity_witness_validates"
                ],
                "operator_identity_witness_rejects_identity_authority_drift": [
                    "operator_identity_witness_rejects_identity_authority_drift"
                ],
                "operator_identity_witness_rejects_missing_requirement": [
                    "operator_identity_witness_rejects_missing_requirement"
                ],
                "operator_identity_witness_rejects_missing_delta_reject": [
                    "operator_identity_witness_rejects_missing_delta_reject"
                ],
                "operator_identity_witness_rejects_constraint_drift": [
                    "operator_identity_witness_rejects_constraint_drift"
                ],
                "operator_identity_witness_rejects_evidence_ref_count_drift": [
                    "operator_identity_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_operator_approval_decision_witness",
            [
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "validate_universal_symbol_receipt_store_operator_approval_decision_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
                "scripts/validate_universal_symbol_receipt_store_operator_identity_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store operator approval decision witness defines operator identity witness, explicit decision value, approval scope, tenant scope, action boundary, expiry/reapproval, revocation path, and audit receipt requirements while denying approval decision recording, approval recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_operator_approval_decision_witness_validates",
                "operator_approval_decision_witness_rejects_decision_authority_drift",
                "operator_approval_decision_witness_rejects_missing_requirement",
                "operator_approval_decision_witness_rejects_missing_delta_reject",
                "operator_approval_decision_witness_rejects_constraint_drift",
                "operator_approval_decision_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_operator_approval_decision_witness_validates": [
                    "foundation_universal_symbol_receipt_store_operator_approval_decision_witness_validates"
                ],
                "operator_approval_decision_witness_rejects_decision_authority_drift": [
                    "operator_approval_decision_witness_rejects_decision_authority_drift"
                ],
                "operator_approval_decision_witness_rejects_missing_requirement": [
                    "operator_approval_decision_witness_rejects_missing_requirement"
                ],
                "operator_approval_decision_witness_rejects_missing_delta_reject": [
                    "operator_approval_decision_witness_rejects_missing_delta_reject"
                ],
                "operator_approval_decision_witness_rejects_constraint_drift": [
                    "operator_approval_decision_witness_rejects_constraint_drift"
                ],
                "operator_approval_decision_witness_rejects_evidence_ref_count_drift": [
                    "operator_approval_decision_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_operator_reapproval_expiry_witness",
            [
                "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
                "validate_universal_symbol_receipt_store_operator_reapproval_expiry_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_operator_reapproval_expiry_witness.py",
                "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store operator reapproval expiry witness defines approval decision ref, issued-at bound, expires-at bound, reapproval window, staleness policy, operator identity witness, revocation check, and audit receipt requirements while denying reapproval expiry binding, approval decision recording, approval recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_operator_reapproval_expiry_witness_validates",
                "operator_reapproval_expiry_witness_rejects_temporal_authority_drift",
                "operator_reapproval_expiry_witness_rejects_missing_requirement",
                "operator_reapproval_expiry_witness_rejects_missing_delta_reject",
                "operator_reapproval_expiry_witness_rejects_constraint_drift",
                "operator_reapproval_expiry_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_operator_reapproval_expiry_witness_validates": [
                    "foundation_universal_symbol_receipt_store_operator_reapproval_expiry_witness_validates"
                ],
                "operator_reapproval_expiry_witness_rejects_temporal_authority_drift": [
                    "operator_reapproval_expiry_witness_rejects_temporal_authority_drift"
                ],
                "operator_reapproval_expiry_witness_rejects_missing_requirement": [
                    "operator_reapproval_expiry_witness_rejects_missing_requirement"
                ],
                "operator_reapproval_expiry_witness_rejects_missing_delta_reject": [
                    "operator_reapproval_expiry_witness_rejects_missing_delta_reject"
                ],
                "operator_reapproval_expiry_witness_rejects_constraint_drift": [
                    "operator_reapproval_expiry_witness_rejects_constraint_drift"
                ],
                "operator_reapproval_expiry_witness_rejects_evidence_ref_count_drift": [
                    "operator_reapproval_expiry_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_operator_revocation_witness",
            [
                "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
                "validate_universal_symbol_receipt_store_operator_revocation_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store operator revocation witness defines operator identity witness, approval decision ref, revocation state, revocation scope, revocation reason, effective-at bound, propagation receipt, and audit receipt requirements while denying revocation binding, approval decision recording, approval recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_operator_revocation_witness_validates",
                "operator_revocation_witness_rejects_revocation_authority_drift",
                "operator_revocation_witness_rejects_missing_requirement",
                "operator_revocation_witness_rejects_missing_delta_reject",
                "operator_revocation_witness_rejects_constraint_drift",
                "operator_revocation_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_operator_revocation_witness_validates": [
                    "foundation_universal_symbol_receipt_store_operator_revocation_witness_validates"
                ],
                "operator_revocation_witness_rejects_revocation_authority_drift": [
                    "operator_revocation_witness_rejects_revocation_authority_drift"
                ],
                "operator_revocation_witness_rejects_missing_requirement": [
                    "operator_revocation_witness_rejects_missing_requirement"
                ],
                "operator_revocation_witness_rejects_missing_delta_reject": [
                    "operator_revocation_witness_rejects_missing_delta_reject"
                ],
                "operator_revocation_witness_rejects_constraint_drift": [
                    "operator_revocation_witness_rejects_constraint_drift"
                ],
                "operator_revocation_witness_rejects_evidence_ref_count_drift": [
                    "operator_revocation_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_reapproval_revocation_witness",
            [
                "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
                "validate_universal_symbol_receipt_store_reapproval_revocation_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_reapproval_revocation_witness.py",
                "scripts/validate_universal_symbol_receipt_store_operator_approval_decision_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store reapproval revocation witness defines approval decision witness, active grant identity, reapproval window, expiry evidence, revocation request, revocation effect boundary, replacement decision path, and lifecycle audit receipt requirements while denying reapproval recording, revocation recording, approval decision recording, approval recording, write-path registration, receipt append, replacement decision recording, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_reapproval_revocation_witness_validates",
                "reapproval_revocation_witness_rejects_lifecycle_authority_drift",
                "reapproval_revocation_witness_rejects_missing_requirement",
                "reapproval_revocation_witness_rejects_missing_delta_reject",
                "reapproval_revocation_witness_rejects_constraint_drift",
                "reapproval_revocation_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_reapproval_revocation_witness_validates": [
                    "foundation_universal_symbol_receipt_store_reapproval_revocation_witness_validates"
                ],
                "reapproval_revocation_witness_rejects_lifecycle_authority_drift": [
                    "reapproval_revocation_witness_rejects_lifecycle_authority_drift"
                ],
                "reapproval_revocation_witness_rejects_missing_requirement": [
                    "reapproval_revocation_witness_rejects_missing_requirement"
                ],
                "reapproval_revocation_witness_rejects_missing_delta_reject": [
                    "reapproval_revocation_witness_rejects_missing_delta_reject"
                ],
                "reapproval_revocation_witness_rejects_constraint_drift": [
                    "reapproval_revocation_witness_rejects_constraint_drift"
                ],
                "reapproval_revocation_witness_rejects_evidence_ref_count_drift": [
                    "reapproval_revocation_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_lifecycle_evidence_receipt",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
                "validate_universal_symbol_receipt_store_lifecycle_evidence_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json",
                "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_reapproval_expiry_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_reapproval_expiry_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "schemas/temporal_reapproval_receipt.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
                "scripts/produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
                "scripts/verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
                "scripts/validate_universal_symbol_receipt_store_operator_reapproval_expiry_witness.py",
                "scripts/validate_universal_symbol_receipt_store_operator_revocation_witness.py",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_receipt.py",
                "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
                "tests/test_produce_universal_symbol_receipt_store_lifecycle_evidence_receipt.py",
                "tests/test_verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
                "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store lifecycle evidence receipt defines active grant identity, reapproval window, expiry evidence, revocation request, revocation effect boundary, replacement decision, and lifecycle audit evidence requirements, with deterministic non-authorizing reference intake and structural ref verification, while denying lifecycle recording, grant extension, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_lifecycle_evidence_receipt_validates",
                "lifecycle_evidence_receipt_rejects_lifecycle_authority_drift",
                "lifecycle_evidence_receipt_rejects_missing_live_evidence_kind",
                "lifecycle_evidence_receipt_rejects_missing_delta_reject",
                "lifecycle_evidence_receipt_rejects_missing_upstream_contract_ref",
                "lifecycle_evidence_receipt_rejects_consistency_drift",
                "lifecycle_evidence_receipt_rejects_evidence_ref_count_drift",
                "lifecycle_evidence_producer_collects_refs_without_authority",
                "lifecycle_evidence_producer_reports_missing_refs",
                "lifecycle_evidence_producer_rejects_unknown_evidence_kind",
                "lifecycle_evidence_producer_rejects_raw_secret_like_ref",
                "verifier_accepts_complete_refs_without_authority",
                "verifier_blocks_template_placeholder_refs",
                "verifier_rejects_missing_repository_relative_ref",
                "verifier_rejects_authority_drift",
                "verifier_rejects_secret_like_ref",
                "verifier_rejects_wrong_scheme_for_evidence_kind",
                "verifier_accepts_matching_local_json_ref_without_authority",
                "verifier_rejects_local_json_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_lifecycle_evidence_receipt_validates": [
                    "foundation_universal_symbol_receipt_store_lifecycle_evidence_receipt_validates"
                ],
                "lifecycle_evidence_receipt_rejects_lifecycle_authority_drift": [
                    "lifecycle_evidence_receipt_rejects_lifecycle_authority_drift"
                ],
                "lifecycle_evidence_receipt_rejects_missing_live_evidence_kind": [
                    "lifecycle_evidence_receipt_rejects_missing_live_evidence_kind"
                ],
                "lifecycle_evidence_receipt_rejects_missing_delta_reject": [
                    "lifecycle_evidence_receipt_rejects_missing_delta_reject"
                ],
                "lifecycle_evidence_receipt_rejects_missing_upstream_contract_ref": [
                    "lifecycle_evidence_receipt_rejects_missing_upstream_contract_ref"
                ],
                "lifecycle_evidence_receipt_rejects_consistency_drift": [
                    "lifecycle_evidence_receipt_rejects_consistency_drift"
                ],
                "lifecycle_evidence_receipt_rejects_evidence_ref_count_drift": [
                    "lifecycle_evidence_receipt_rejects_evidence_ref_count_drift"
                ],
                "lifecycle_evidence_producer_collects_refs_without_authority": [
                    "lifecycle_evidence_producer_collects_refs_without_authority"
                ],
                "lifecycle_evidence_producer_reports_missing_refs": [
                    "lifecycle_evidence_producer_reports_missing_refs"
                ],
                "lifecycle_evidence_producer_rejects_unknown_evidence_kind": [
                    "lifecycle_evidence_producer_rejects_unknown_evidence_kind"
                ],
                "lifecycle_evidence_producer_rejects_raw_secret_like_ref": [
                    "lifecycle_evidence_producer_rejects_raw_secret_like_ref"
                ],
                "verifier_accepts_complete_refs_without_authority": [
                    "verifier_accepts_complete_refs_without_authority"
                ],
                "verifier_blocks_template_placeholder_refs": [
                    "verifier_blocks_template_placeholder_refs"
                ],
                "verifier_rejects_missing_repository_relative_ref": [
                    "verifier_rejects_missing_repository_relative_ref"
                ],
                "verifier_rejects_authority_drift": [
                    "verifier_rejects_authority_drift"
                ],
                "verifier_rejects_secret_like_ref": [
                    "verifier_rejects_secret_like_ref"
                ],
                "verifier_rejects_wrong_scheme_for_evidence_kind": [
                    "verifier_rejects_wrong_scheme_for_evidence_kind"
                ],
                "verifier_accepts_matching_local_json_ref_without_authority": [
                    "verifier_accepts_matching_local_json_ref_without_authority"
                ],
                "verifier_rejects_local_json_authority_drift": [
                    "verifier_rejects_local_json_authority_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_lifecycle_evidence_bundle",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json",
                "validate_universal_symbol_receipt_store_lifecycle_evidence_bundle",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_receipt.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
                "scripts/verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
                "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
                "tests/test_verify_universal_symbol_receipt_store_lifecycle_evidence_refs.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store lifecycle evidence bundle carries the seven lifecycle evidence refs and verifier outcomes as a non-authorizing packet while denying lifecycle recording, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_lifecycle_evidence_bundle_validates",
                "build_lifecycle_evidence_bundle_from_verifier_report",
                "lifecycle_evidence_bundle_rejects_authority_drift",
                "lifecycle_evidence_bundle_rejects_missing_evidence_kind",
                "lifecycle_evidence_bundle_rejects_placeholder_content_verified",
                "lifecycle_evidence_bundle_rejects_scheme_content_verified",
                "lifecycle_evidence_bundle_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_lifecycle_evidence_bundle_validates": [
                    "foundation_lifecycle_evidence_bundle_validates"
                ],
                "build_lifecycle_evidence_bundle_from_verifier_report": [
                    "build_lifecycle_evidence_bundle_from_verifier_report"
                ],
                "lifecycle_evidence_bundle_rejects_authority_drift": [
                    "lifecycle_evidence_bundle_rejects_authority_drift"
                ],
                "lifecycle_evidence_bundle_rejects_missing_evidence_kind": [
                    "lifecycle_evidence_bundle_rejects_missing_evidence_kind"
                ],
                "lifecycle_evidence_bundle_rejects_placeholder_content_verified": [
                    "lifecycle_evidence_bundle_rejects_placeholder_content_verified"
                ],
                "lifecycle_evidence_bundle_rejects_scheme_content_verified": [
                    "lifecycle_evidence_bundle_rejects_scheme_content_verified"
                ],
                "lifecycle_evidence_bundle_rejects_evidence_ref_count_drift": [
                    "lifecycle_evidence_bundle_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_evidence_bundle.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_evidence_bundle.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
                "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model.py",
                "tests/test_validate_universal_symbol_receipt_store_lifecycle_evidence_bundle.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store lifecycle evidence bundle read model exposes simple operator status and bounded evidence-kind rows while remaining read-only and denying lifecycle authority, raw detail exposure, receipt append, mutation, and terminal closure.",
            [
                "foundation_lifecycle_evidence_bundle_read_model_validates",
                "lifecycle_evidence_bundle_read_model_rejects_authority_drift",
                "lifecycle_evidence_bundle_read_model_rejects_raw_detail_visibility",
                "lifecycle_evidence_bundle_read_model_rejects_missing_evidence_kind",
                "lifecycle_evidence_bundle_read_model_rejects_placeholder_content_verified",
                "lifecycle_evidence_bundle_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_lifecycle_evidence_bundle_read_model_validates": [
                    "foundation_lifecycle_evidence_bundle_read_model_validates"
                ],
                "lifecycle_evidence_bundle_read_model_rejects_authority_drift": [
                    "lifecycle_evidence_bundle_read_model_rejects_authority_drift"
                ],
                "lifecycle_evidence_bundle_read_model_rejects_raw_detail_visibility": [
                    "lifecycle_evidence_bundle_read_model_rejects_raw_detail_visibility"
                ],
                "lifecycle_evidence_bundle_read_model_rejects_missing_evidence_kind": [
                    "lifecycle_evidence_bundle_read_model_rejects_missing_evidence_kind"
                ],
                "lifecycle_evidence_bundle_read_model_rejects_placeholder_content_verified": [
                    "lifecycle_evidence_bundle_read_model_rejects_placeholder_content_verified"
                ],
                "lifecycle_evidence_bundle_read_model_rejects_evidence_ref_count_drift": [
                    "lifecycle_evidence_bundle_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_lifecycle_audit_receipt",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "validate_universal_symbol_receipt_store_lifecycle_audit_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_audit_receipt.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store lifecycle audit receipt defines source lifecycle witness, approval decision witness, active grant ref, lifecycle event kind, before/after authority envelope, Delta_reject ledger, redaction/digest binding, and auditor identity requirements while denying lifecycle audit recording, reapproval recording, revocation recording, receipt append, replacement decision recording, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_receipt_store_lifecycle_audit_receipt_validates",
                "lifecycle_audit_receipt_rejects_lifecycle_authority_drift",
                "lifecycle_audit_receipt_rejects_missing_requirement",
                "lifecycle_audit_receipt_rejects_missing_delta_reject",
                "lifecycle_audit_receipt_rejects_constraint_drift",
                "lifecycle_audit_receipt_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_lifecycle_audit_receipt_validates": [
                    "foundation_universal_symbol_receipt_store_lifecycle_audit_receipt_validates"
                ],
                "lifecycle_audit_receipt_rejects_lifecycle_authority_drift": [
                    "lifecycle_audit_receipt_rejects_lifecycle_authority_drift"
                ],
                "lifecycle_audit_receipt_rejects_missing_requirement": [
                    "lifecycle_audit_receipt_rejects_missing_requirement"
                ],
                "lifecycle_audit_receipt_rejects_missing_delta_reject": [
                    "lifecycle_audit_receipt_rejects_missing_delta_reject"
                ],
                "lifecycle_audit_receipt_rejects_constraint_drift": [
                    "lifecycle_audit_receipt_rejects_constraint_drift"
                ],
                "lifecycle_audit_receipt_rejects_evidence_ref_count_drift": [
                    "lifecycle_audit_receipt_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_lifecycle_audit_read_model",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_audit_read_model.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_lifecycle_audit_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_lifecycle_audit_read_model.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_audit_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_lifecycle_audit_receipt.py",
                "tests/test_validate_universal_symbol_receipt_store_lifecycle_audit_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store lifecycle audit read model exposes blocked audit status and bounded requirement rows while remaining read-only and denying lifecycle audit authority, raw detail exposure, receipt append, mutation, terminal closure, and production readiness.",
            [
                "foundation_lifecycle_audit_read_model_validates",
                "lifecycle_audit_read_model_rejects_authority_drift",
                "lifecycle_audit_read_model_rejects_raw_detail_visibility",
                "lifecycle_audit_read_model_rejects_missing_requirement",
                "lifecycle_audit_read_model_rejects_duplicate_requirement_row",
                "lifecycle_audit_read_model_rejects_missing_delta_reject_log",
                "lifecycle_audit_read_model_rejects_receipt_projection_drift",
                "lifecycle_audit_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_lifecycle_audit_read_model_validates": [
                    "foundation_lifecycle_audit_read_model_validates"
                ],
                "lifecycle_audit_read_model_rejects_authority_drift": [
                    "lifecycle_audit_read_model_rejects_authority_drift"
                ],
                "lifecycle_audit_read_model_rejects_raw_detail_visibility": [
                    "lifecycle_audit_read_model_rejects_raw_detail_visibility"
                ],
                "lifecycle_audit_read_model_rejects_missing_requirement": [
                    "lifecycle_audit_read_model_rejects_missing_requirement"
                ],
                "lifecycle_audit_read_model_rejects_duplicate_requirement_row": [
                    "lifecycle_audit_read_model_rejects_duplicate_requirement_row"
                ],
                "lifecycle_audit_read_model_rejects_missing_delta_reject_log": [
                    "lifecycle_audit_read_model_rejects_missing_delta_reject_log"
                ],
                "lifecycle_audit_read_model_rejects_receipt_projection_drift": [
                    "lifecycle_audit_read_model_rejects_receipt_projection_drift"
                ],
                "lifecycle_audit_read_model_rejects_evidence_ref_count_drift": [
                    "lifecycle_audit_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_replacement_decision_receipt",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "validate_universal_symbol_receipt_store_replacement_decision_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_reapproval_revocation_witness.schema.json",
                "examples/universal_symbol_receipt_store_reapproval_revocation_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_decision_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_decision_witness.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_receipt.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store replacement decision receipt defines superseded approval decision, replacement approval decision, replacement reason, scope equivalence, tenant continuity, revocation link, lifecycle audit link, and Delta_reject ledger requirements while denying replacement decision recording, approval decision recording, revocation recording, lifecycle audit recording, receipt append, write-path registration, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, terminal closure, and production readiness.",
            [
                "foundation_universal_symbol_receipt_store_replacement_decision_receipt_validates",
                "replacement_decision_receipt_rejects_decision_authority_drift",
                "replacement_decision_receipt_rejects_missing_requirement",
                "replacement_decision_receipt_rejects_missing_delta_reject",
                "replacement_decision_receipt_rejects_constraint_drift",
                "replacement_decision_receipt_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_replacement_decision_receipt_validates": [
                    "foundation_universal_symbol_receipt_store_replacement_decision_receipt_validates"
                ],
                "replacement_decision_receipt_rejects_decision_authority_drift": [
                    "replacement_decision_receipt_rejects_decision_authority_drift"
                ],
                "replacement_decision_receipt_rejects_missing_requirement": [
                    "replacement_decision_receipt_rejects_missing_requirement"
                ],
                "replacement_decision_receipt_rejects_missing_delta_reject": [
                    "replacement_decision_receipt_rejects_missing_delta_reject"
                ],
                "replacement_decision_receipt_rejects_constraint_drift": [
                    "replacement_decision_receipt_rejects_constraint_drift"
                ],
                "replacement_decision_receipt_rejects_evidence_ref_count_drift": [
                    "replacement_decision_receipt_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_replacement_decision_read_model",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_read_model.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_replacement_decision_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_read_model.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_receipt.py",
                "tests/test_validate_universal_symbol_receipt_store_replacement_decision_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store replacement decision read model exposes blocked replacement status and bounded requirement rows while remaining read-only and denying decision authority, raw detail exposure, receipt append, mutation, terminal closure, and production readiness.",
            [
                "foundation_replacement_decision_read_model_validates",
                "replacement_decision_read_model_rejects_authority_drift",
                "replacement_decision_read_model_rejects_raw_detail_visibility",
                "replacement_decision_read_model_rejects_missing_requirement",
                "replacement_decision_read_model_rejects_duplicate_requirement_row",
                "replacement_decision_read_model_rejects_missing_delta_reject_log",
                "replacement_decision_read_model_rejects_receipt_projection_drift",
                "replacement_decision_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_replacement_decision_read_model_validates": [
                    "foundation_replacement_decision_read_model_validates"
                ],
                "replacement_decision_read_model_rejects_authority_drift": [
                    "replacement_decision_read_model_rejects_authority_drift"
                ],
                "replacement_decision_read_model_rejects_raw_detail_visibility": [
                    "replacement_decision_read_model_rejects_raw_detail_visibility"
                ],
                "replacement_decision_read_model_rejects_missing_requirement": [
                    "replacement_decision_read_model_rejects_missing_requirement"
                ],
                "replacement_decision_read_model_rejects_duplicate_requirement_row": [
                    "replacement_decision_read_model_rejects_duplicate_requirement_row"
                ],
                "replacement_decision_read_model_rejects_missing_delta_reject_log": [
                    "replacement_decision_read_model_rejects_missing_delta_reject_log"
                ],
                "replacement_decision_read_model_rejects_receipt_projection_drift": [
                    "replacement_decision_read_model_rejects_receipt_projection_drift"
                ],
                "replacement_decision_read_model_rejects_evidence_ref_count_drift": [
                    "replacement_decision_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.foundation.json",
                "validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_receipt.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_receipt.foundation.json",
                "schemas/universal_symbol_receipt_store_lifecycle_audit_receipt.schema.json",
                "examples/universal_symbol_receipt_store_lifecycle_audit_receipt.foundation.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store replacement decision replay idempotency witness defines replacement decision receipt binding, deterministic idempotency key, canonical replay input, decision digest binding, tenant/scope digest, replay cursor, duplicate-effect denial, and audit receipt requirements while denying replay binding, idempotency acceptance, replacement recording, receipt append, replay state commit, duplicate effects, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness_validates",
                "replacement_replay_idempotency_witness_rejects_replay_authority_drift",
                "replacement_replay_idempotency_witness_rejects_missing_requirement",
                "replacement_replay_idempotency_witness_rejects_missing_delta_reject",
                "replacement_replay_idempotency_witness_rejects_constraint_drift",
                "replacement_replay_idempotency_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness_validates": [
                    "foundation_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness_validates"
                ],
                "replacement_replay_idempotency_witness_rejects_replay_authority_drift": [
                    "replacement_replay_idempotency_witness_rejects_replay_authority_drift"
                ],
                "replacement_replay_idempotency_witness_rejects_missing_requirement": [
                    "replacement_replay_idempotency_witness_rejects_missing_requirement"
                ],
                "replacement_replay_idempotency_witness_rejects_missing_delta_reject": [
                    "replacement_replay_idempotency_witness_rejects_missing_delta_reject"
                ],
                "replacement_replay_idempotency_witness_rejects_constraint_drift": [
                    "replacement_replay_idempotency_witness_rejects_constraint_drift"
                ],
                "replacement_replay_idempotency_witness_rejects_evidence_ref_count_drift": [
                    "replacement_replay_idempotency_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store replacement decision replay/idempotency read model exposes blocked replay status and bounded requirement rows while remaining read-only and denying replay authority, idempotency acceptance, replay state commit, duplicate effects, raw detail exposure, receipt append, mutation, and terminal closure.",
            [
                "foundation_replacement_replay_read_model_validates",
                "replacement_replay_read_model_rejects_authority_drift",
                "replacement_replay_read_model_rejects_raw_detail_visibility",
                "replacement_replay_read_model_rejects_missing_requirement",
                "replacement_replay_read_model_rejects_duplicate_requirement_row",
                "replacement_replay_read_model_rejects_missing_delta_reject_log",
                "replacement_replay_read_model_rejects_witness_projection_drift",
                "replacement_replay_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_replacement_replay_read_model_validates": [
                    "foundation_replacement_replay_read_model_validates"
                ],
                "replacement_replay_read_model_rejects_authority_drift": [
                    "replacement_replay_read_model_rejects_authority_drift"
                ],
                "replacement_replay_read_model_rejects_raw_detail_visibility": [
                    "replacement_replay_read_model_rejects_raw_detail_visibility"
                ],
                "replacement_replay_read_model_rejects_missing_requirement": [
                    "replacement_replay_read_model_rejects_missing_requirement"
                ],
                "replacement_replay_read_model_rejects_duplicate_requirement_row": [
                    "replacement_replay_read_model_rejects_duplicate_requirement_row"
                ],
                "replacement_replay_read_model_rejects_missing_delta_reject_log": [
                    "replacement_replay_read_model_rejects_missing_delta_reject_log"
                ],
                "replacement_replay_read_model_rejects_witness_projection_drift": [
                    "replacement_replay_read_model_rejects_witness_projection_drift"
                ],
                "replacement_replay_read_model_rejects_evidence_ref_count_drift": [
                    "replacement_replay_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_tenant_scope_witness",
            [
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "validate_universal_symbol_receipt_store_tenant_scope_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store tenant scope witness defines tenant identity, actor identity, tenant-actor binding, receipt-store partition, cross-tenant isolation, tenant policy, audit receipt, and rebinding or revocation requirements while denying tenant binding, approval recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_tenant_scope_witness_validates",
                "tenant_scope_witness_rejects_tenant_authority_drift",
                "tenant_scope_witness_rejects_missing_requirement",
                "tenant_scope_witness_rejects_missing_delta_reject",
                "tenant_scope_witness_rejects_constraint_drift",
                "tenant_scope_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_tenant_scope_witness_validates": [
                    "foundation_universal_symbol_receipt_store_tenant_scope_witness_validates"
                ],
                "tenant_scope_witness_rejects_tenant_authority_drift": [
                    "tenant_scope_witness_rejects_tenant_authority_drift"
                ],
                "tenant_scope_witness_rejects_missing_requirement": [
                    "tenant_scope_witness_rejects_missing_requirement"
                ],
                "tenant_scope_witness_rejects_missing_delta_reject": [
                    "tenant_scope_witness_rejects_missing_delta_reject"
                ],
                "tenant_scope_witness_rejects_constraint_drift": [
                    "tenant_scope_witness_rejects_constraint_drift"
                ],
                "tenant_scope_witness_rejects_evidence_ref_count_drift": [
                    "tenant_scope_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_tenant_scope_read_model",
            [
                "schemas/universal_symbol_receipt_store_tenant_scope_read_model.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_tenant_scope_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_tenant_scope_read_model.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_tenant_scope_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store tenant scope read model projects blocked tenant scope status, tenant requirement rows, Delta_reject logging state, raw-detail visibility denial, and effective denial fields while denying tenant authority, tenant binding, receipt append, raw payload exposure, raw secret exposure, mutation, terminal closure, and success claims.",
            [
                "foundation_tenant_scope_read_model_validates",
                "tenant_scope_read_model_rejects_authority_drift",
                "tenant_scope_read_model_rejects_raw_detail_visibility",
                "tenant_scope_read_model_rejects_missing_requirement",
                "tenant_scope_read_model_rejects_duplicate_requirement_row",
                "tenant_scope_read_model_rejects_missing_delta_reject_log",
                "tenant_scope_read_model_rejects_witness_projection_drift",
                "tenant_scope_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_tenant_scope_read_model_validates": ["foundation_tenant_scope_read_model_validates"],
                "tenant_scope_read_model_rejects_authority_drift": [
                    "tenant_scope_read_model_rejects_authority_drift"
                ],
                "tenant_scope_read_model_rejects_raw_detail_visibility": [
                    "tenant_scope_read_model_rejects_raw_detail_visibility"
                ],
                "tenant_scope_read_model_rejects_missing_requirement": [
                    "tenant_scope_read_model_rejects_missing_requirement"
                ],
                "tenant_scope_read_model_rejects_duplicate_requirement_row": [
                    "tenant_scope_read_model_rejects_duplicate_requirement_row"
                ],
                "tenant_scope_read_model_rejects_missing_delta_reject_log": [
                    "tenant_scope_read_model_rejects_missing_delta_reject_log"
                ],
                "tenant_scope_read_model_rejects_witness_projection_drift": [
                    "tenant_scope_read_model_rejects_witness_projection_drift"
                ],
                "tenant_scope_read_model_rejects_evidence_ref_count_drift": [
                    "tenant_scope_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_writer_duty_scope_witness",
            [
                "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
                "validate_universal_symbol_receipt_store_writer_duty_scope_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store writer duty scope witness defines writer role identity, permitted receipt kinds, permitted action scope, denied action scope, separation-of-duties, tenant-scope link, audit receipt, and revocation or rebinding requirements while denying duty binding, tenant binding, approval recording, writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_writer_duty_scope_witness_validates",
                "writer_duty_scope_witness_rejects_duty_authority_drift",
                "writer_duty_scope_witness_rejects_missing_requirement",
                "writer_duty_scope_witness_rejects_missing_delta_reject",
                "writer_duty_scope_witness_rejects_constraint_drift",
                "writer_duty_scope_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_writer_duty_scope_witness_validates": [
                    "foundation_universal_symbol_receipt_store_writer_duty_scope_witness_validates"
                ],
                "writer_duty_scope_witness_rejects_duty_authority_drift": [
                    "writer_duty_scope_witness_rejects_duty_authority_drift"
                ],
                "writer_duty_scope_witness_rejects_missing_requirement": [
                    "writer_duty_scope_witness_rejects_missing_requirement"
                ],
                "writer_duty_scope_witness_rejects_missing_delta_reject": [
                    "writer_duty_scope_witness_rejects_missing_delta_reject"
                ],
                "writer_duty_scope_witness_rejects_constraint_drift": [
                    "writer_duty_scope_witness_rejects_constraint_drift"
                ],
                "writer_duty_scope_witness_rejects_evidence_ref_count_drift": [
                    "writer_duty_scope_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_writer_duty_scope_read_model",
            [
                "schemas/universal_symbol_receipt_store_writer_duty_scope_read_model.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_writer_duty_scope_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_writer_duty_scope_read_model.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_writer_duty_scope_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store writer duty scope read model projects blocked writer duty scope status, duty requirement rows, Delta_reject logging state, raw-detail visibility denial, and effective denial fields while denying duty authority, duty binding, tenant binding, receipt append, raw payload exposure, raw secret exposure, mutation, terminal closure, and success claims.",
            [
                "foundation_writer_duty_scope_read_model_validates",
                "writer_duty_scope_read_model_rejects_authority_drift",
                "writer_duty_scope_read_model_rejects_raw_detail_visibility",
                "writer_duty_scope_read_model_rejects_missing_requirement",
                "writer_duty_scope_read_model_rejects_duplicate_requirement_row",
                "writer_duty_scope_read_model_rejects_missing_delta_reject_log",
                "writer_duty_scope_read_model_rejects_witness_projection_drift",
                "writer_duty_scope_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_writer_duty_scope_read_model_validates": [
                    "foundation_writer_duty_scope_read_model_validates"
                ],
                "writer_duty_scope_read_model_rejects_authority_drift": [
                    "writer_duty_scope_read_model_rejects_authority_drift"
                ],
                "writer_duty_scope_read_model_rejects_raw_detail_visibility": [
                    "writer_duty_scope_read_model_rejects_raw_detail_visibility"
                ],
                "writer_duty_scope_read_model_rejects_missing_requirement": [
                    "writer_duty_scope_read_model_rejects_missing_requirement"
                ],
                "writer_duty_scope_read_model_rejects_duplicate_requirement_row": [
                    "writer_duty_scope_read_model_rejects_duplicate_requirement_row"
                ],
                "writer_duty_scope_read_model_rejects_missing_delta_reject_log": [
                    "writer_duty_scope_read_model_rejects_missing_delta_reject_log"
                ],
                "writer_duty_scope_read_model_rejects_witness_projection_drift": [
                    "writer_duty_scope_read_model_rejects_witness_projection_drift"
                ],
                "writer_duty_scope_read_model_rejects_evidence_ref_count_drift": [
                    "writer_duty_scope_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_path_confinement_witness",
            [
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "validate_universal_symbol_receipt_store_path_confinement_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_path_confinement_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store path confinement witness defines canonical root, allowed namespace, traversal denial, symlink resolution, reserved path denial, tenant partition, append-only custody, and audit receipt requirements while denying path confinement, path custody registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, filesystem escape, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_path_confinement_witness_validates",
                "path_confinement_witness_rejects_path_authority_drift",
                "path_confinement_witness_rejects_missing_requirement",
                "path_confinement_witness_rejects_missing_delta_reject",
                "path_confinement_witness_rejects_constraint_drift",
                "path_confinement_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_path_confinement_witness_validates": [
                    "foundation_universal_symbol_receipt_store_path_confinement_witness_validates"
                ],
                "path_confinement_witness_rejects_path_authority_drift": [
                    "path_confinement_witness_rejects_path_authority_drift"
                ],
                "path_confinement_witness_rejects_missing_requirement": [
                    "path_confinement_witness_rejects_missing_requirement"
                ],
                "path_confinement_witness_rejects_missing_delta_reject": [
                    "path_confinement_witness_rejects_missing_delta_reject"
                ],
                "path_confinement_witness_rejects_constraint_drift": [
                    "path_confinement_witness_rejects_constraint_drift"
                ],
                "path_confinement_witness_rejects_evidence_ref_count_drift": [
                    "path_confinement_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_path_confinement_read_model",
            [
                "schemas/universal_symbol_receipt_store_path_confinement_read_model.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_path_confinement_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_path_confinement_read_model.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_path_confinement_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_path_confinement_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_path_confinement_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store path confinement read model projects blocked path confinement status, confinement requirement rows, Delta_reject logging state, raw-detail visibility denial, filesystem escape denial, and effective denial fields while denying path authority, path confinement binding, path custody registration, receipt append, raw payload exposure, raw secret exposure, mutation, terminal closure, and success claims.",
            [
                "foundation_path_confinement_read_model_validates",
                "path_confinement_read_model_rejects_authority_drift",
                "path_confinement_read_model_rejects_filesystem_escape_drift",
                "path_confinement_read_model_rejects_raw_detail_visibility",
                "path_confinement_read_model_rejects_missing_requirement",
                "path_confinement_read_model_rejects_duplicate_requirement_row",
                "path_confinement_read_model_rejects_missing_delta_reject_log",
                "path_confinement_read_model_rejects_witness_projection_drift",
                "path_confinement_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_path_confinement_read_model_validates": [
                    "foundation_path_confinement_read_model_validates"
                ],
                "path_confinement_read_model_rejects_authority_drift": [
                    "path_confinement_read_model_rejects_authority_drift"
                ],
                "path_confinement_read_model_rejects_filesystem_escape_drift": [
                    "path_confinement_read_model_rejects_filesystem_escape_drift"
                ],
                "path_confinement_read_model_rejects_raw_detail_visibility": [
                    "path_confinement_read_model_rejects_raw_detail_visibility"
                ],
                "path_confinement_read_model_rejects_missing_requirement": [
                    "path_confinement_read_model_rejects_missing_requirement"
                ],
                "path_confinement_read_model_rejects_duplicate_requirement_row": [
                    "path_confinement_read_model_rejects_duplicate_requirement_row"
                ],
                "path_confinement_read_model_rejects_missing_delta_reject_log": [
                    "path_confinement_read_model_rejects_missing_delta_reject_log"
                ],
                "path_confinement_read_model_rejects_witness_projection_drift": [
                    "path_confinement_read_model_rejects_witness_projection_drift"
                ],
                "path_confinement_read_model_rejects_evidence_ref_count_drift": [
                    "path_confinement_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_write_path_idempotency_witness",
            [
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "validate_universal_symbol_receipt_store_write_path_idempotency_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py",
                "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store write-path idempotency witness defines deterministic key derivation, canonical input, tenant/actor binding, write-path binding, payload digest binding, replay collision checks, duplicate-effect denial, and audit receipt requirements while denying idempotency binding, write-path registration, path custody registration, receipt append, duplicate append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_write_path_idempotency_witness_validates",
                "write_path_idempotency_witness_rejects_append_authority_drift",
                "write_path_idempotency_witness_rejects_missing_requirement",
                "write_path_idempotency_witness_rejects_missing_delta_reject",
                "write_path_idempotency_witness_rejects_constraint_drift",
                "write_path_idempotency_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_write_path_idempotency_witness_validates": [
                    "foundation_universal_symbol_receipt_store_write_path_idempotency_witness_validates"
                ],
                "write_path_idempotency_witness_rejects_append_authority_drift": [
                    "write_path_idempotency_witness_rejects_append_authority_drift"
                ],
                "write_path_idempotency_witness_rejects_missing_requirement": [
                    "write_path_idempotency_witness_rejects_missing_requirement"
                ],
                "write_path_idempotency_witness_rejects_missing_delta_reject": [
                    "write_path_idempotency_witness_rejects_missing_delta_reject"
                ],
                "write_path_idempotency_witness_rejects_constraint_drift": [
                    "write_path_idempotency_witness_rejects_constraint_drift"
                ],
                "write_path_idempotency_witness_rejects_evidence_ref_count_drift": [
                    "write_path_idempotency_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_write_path_idempotency_read_model",
            [
                "schemas/universal_symbol_receipt_store_write_path_idempotency_read_model.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_write_path_idempotency_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_write_path_idempotency_read_model.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_write_path_idempotency_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store write-path idempotency read model projects blocked idempotency status, idempotency requirement rows, Delta_reject logging state, raw-detail visibility denial, duplicate append denial, and effective denial fields while denying idempotency authority, write-path registration, path custody registration, receipt append, raw payload exposure, raw secret exposure, mutation, terminal closure, and success claims.",
            [
                "foundation_write_path_idempotency_read_model_validates",
                "write_path_idempotency_read_model_rejects_authority_drift",
                "write_path_idempotency_read_model_rejects_duplicate_append_drift",
                "write_path_idempotency_read_model_rejects_raw_detail_visibility",
                "write_path_idempotency_read_model_rejects_missing_requirement",
                "write_path_idempotency_read_model_rejects_duplicate_requirement_row",
                "write_path_idempotency_read_model_rejects_missing_delta_reject_log",
                "write_path_idempotency_read_model_rejects_witness_projection_drift",
                "write_path_idempotency_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_write_path_idempotency_read_model_validates": [
                    "foundation_write_path_idempotency_read_model_validates"
                ],
                "write_path_idempotency_read_model_rejects_authority_drift": [
                    "write_path_idempotency_read_model_rejects_authority_drift"
                ],
                "write_path_idempotency_read_model_rejects_duplicate_append_drift": [
                    "write_path_idempotency_read_model_rejects_duplicate_append_drift"
                ],
                "write_path_idempotency_read_model_rejects_raw_detail_visibility": [
                    "write_path_idempotency_read_model_rejects_raw_detail_visibility"
                ],
                "write_path_idempotency_read_model_rejects_missing_requirement": [
                    "write_path_idempotency_read_model_rejects_missing_requirement"
                ],
                "write_path_idempotency_read_model_rejects_duplicate_requirement_row": [
                    "write_path_idempotency_read_model_rejects_duplicate_requirement_row"
                ],
                "write_path_idempotency_read_model_rejects_missing_delta_reject_log": [
                    "write_path_idempotency_read_model_rejects_missing_delta_reject_log"
                ],
                "write_path_idempotency_read_model_rejects_witness_projection_drift": [
                    "write_path_idempotency_read_model_rejects_witness_projection_drift"
                ],
                "write_path_idempotency_read_model_rejects_evidence_ref_count_drift": [
                    "write_path_idempotency_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_durability_replay_witness",
            [
                "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
                "validate_universal_symbol_receipt_store_durability_replay_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store durability replay witness defines ordered replay, append sequence, digest chain, idempotency key reuse, crash-window, durability receipt, rollback handoff, and audit receipt requirements while denying durability replay binding, write-path registration, receipt append, replay execution, duplicate effects, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_durability_replay_witness_validates",
                "durability_replay_witness_rejects_append_authority_drift",
                "durability_replay_witness_rejects_missing_requirement",
                "durability_replay_witness_rejects_missing_delta_reject",
                "durability_replay_witness_rejects_constraint_drift",
                "durability_replay_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_durability_replay_witness_validates": [
                    "foundation_universal_symbol_receipt_store_durability_replay_witness_validates"
                ],
                "durability_replay_witness_rejects_append_authority_drift": [
                    "durability_replay_witness_rejects_append_authority_drift"
                ],
                "durability_replay_witness_rejects_missing_requirement": [
                    "durability_replay_witness_rejects_missing_requirement"
                ],
                "durability_replay_witness_rejects_missing_delta_reject": [
                    "durability_replay_witness_rejects_missing_delta_reject"
                ],
                "durability_replay_witness_rejects_constraint_drift": [
                    "durability_replay_witness_rejects_constraint_drift"
                ],
                "durability_replay_witness_rejects_evidence_ref_count_drift": [
                    "durability_replay_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_durability_replay_read_model",
            [
                "schemas/universal_symbol_receipt_store_durability_replay_read_model.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_durability_replay_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_durability_replay_read_model.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_durability_replay_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_durability_replay_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store durability replay read model projects blocked replay status, durability replay requirement rows, Delta_reject logging state, raw-detail visibility denial, replay execution denial, and effective denial fields while denying replay authority, durability replay binding, write-path registration, receipt append, raw payload exposure, raw secret exposure, mutation, terminal closure, and success claims.",
            [
                "foundation_durability_replay_read_model_validates",
                "durability_replay_read_model_rejects_authority_drift",
                "durability_replay_read_model_rejects_replay_execution_drift",
                "durability_replay_read_model_rejects_raw_detail_visibility",
                "durability_replay_read_model_rejects_missing_requirement",
                "durability_replay_read_model_rejects_duplicate_requirement_row",
                "durability_replay_read_model_rejects_missing_delta_reject_log",
                "durability_replay_read_model_rejects_witness_projection_drift",
                "durability_replay_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_durability_replay_read_model_validates": [
                    "foundation_durability_replay_read_model_validates"
                ],
                "durability_replay_read_model_rejects_authority_drift": [
                    "durability_replay_read_model_rejects_authority_drift"
                ],
                "durability_replay_read_model_rejects_replay_execution_drift": [
                    "durability_replay_read_model_rejects_replay_execution_drift"
                ],
                "durability_replay_read_model_rejects_raw_detail_visibility": [
                    "durability_replay_read_model_rejects_raw_detail_visibility"
                ],
                "durability_replay_read_model_rejects_missing_requirement": [
                    "durability_replay_read_model_rejects_missing_requirement"
                ],
                "durability_replay_read_model_rejects_duplicate_requirement_row": [
                    "durability_replay_read_model_rejects_duplicate_requirement_row"
                ],
                "durability_replay_read_model_rejects_missing_delta_reject_log": [
                    "durability_replay_read_model_rejects_missing_delta_reject_log"
                ],
                "durability_replay_read_model_rejects_witness_projection_drift": [
                    "durability_replay_read_model_rejects_witness_projection_drift"
                ],
                "durability_replay_read_model_rejects_evidence_ref_count_drift": [
                    "durability_replay_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_recovery_witness",
            [
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "validate_universal_symbol_receipt_store_recovery_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_recovery_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store recovery witness defines recovery plan, rollback plan, compensation plan, recovery snapshot, durability replay binding, effect boundary, incident handoff, and post-recovery audit requirements while denying recovery binding, recovery execution, rollback execution, compensation execution, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_recovery_witness_validates",
                "recovery_witness_rejects_execution_authority_drift",
                "recovery_witness_rejects_missing_requirement",
                "recovery_witness_rejects_missing_delta_reject",
                "recovery_witness_rejects_constraint_drift",
                "recovery_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_recovery_witness_validates": [
                    "foundation_universal_symbol_receipt_store_recovery_witness_validates"
                ],
                "recovery_witness_rejects_execution_authority_drift": [
                    "recovery_witness_rejects_execution_authority_drift"
                ],
                "recovery_witness_rejects_missing_requirement": [
                    "recovery_witness_rejects_missing_requirement"
                ],
                "recovery_witness_rejects_missing_delta_reject": [
                    "recovery_witness_rejects_missing_delta_reject"
                ],
                "recovery_witness_rejects_constraint_drift": [
                    "recovery_witness_rejects_constraint_drift"
                ],
                "recovery_witness_rejects_evidence_ref_count_drift": [
                    "recovery_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_recovery_read_model",
            [
                "schemas/universal_symbol_receipt_store_recovery_read_model.schema.json",
                "examples/universal_symbol_receipt_store_recovery_read_model.foundation.json",
                "validate_universal_symbol_receipt_store_recovery_read_model",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_recovery_read_model.schema.json",
                "examples/universal_symbol_receipt_store_recovery_read_model.foundation.json",
                "schemas/universal_symbol_receipt_store_recovery_witness.schema.json",
                "examples/universal_symbol_receipt_store_recovery_witness.foundation.json",
                "scripts/validate_universal_symbol_receipt_store_recovery_read_model.py",
                "scripts/validate_universal_symbol_receipt_store_recovery_witness.py",
                "tests/test_validate_universal_symbol_receipt_store_recovery_read_model.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store recovery read model projects blocked recovery status, recovery requirement rows, Delta_reject logging state, raw-detail visibility denial, recovery execution denial, rollback execution denial, compensation execution denial, replay-state commit denial, and effective denial fields while denying recovery authority, recovery binding, write-path registration, receipt append, raw payload exposure, raw secret exposure, mutation, terminal closure, and success claims.",
            [
                "foundation_recovery_read_model_validates",
                "recovery_read_model_rejects_authority_drift",
                "recovery_read_model_rejects_recovery_execution_drift",
                "recovery_read_model_rejects_rollback_compensation_and_replay_commit_drift",
                "recovery_read_model_rejects_raw_detail_visibility",
                "recovery_read_model_rejects_missing_requirement",
                "recovery_read_model_rejects_duplicate_requirement_row",
                "recovery_read_model_rejects_missing_delta_reject_log",
                "recovery_read_model_rejects_witness_projection_drift",
                "recovery_read_model_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_recovery_read_model_validates": [
                    "foundation_recovery_read_model_validates"
                ],
                "recovery_read_model_rejects_authority_drift": [
                    "recovery_read_model_rejects_authority_drift"
                ],
                "recovery_read_model_rejects_recovery_execution_drift": [
                    "recovery_read_model_rejects_recovery_execution_drift"
                ],
                "recovery_read_model_rejects_rollback_compensation_and_replay_commit_drift": [
                    "recovery_read_model_rejects_rollback_compensation_and_replay_commit_drift"
                ],
                "recovery_read_model_rejects_raw_detail_visibility": [
                    "recovery_read_model_rejects_raw_detail_visibility"
                ],
                "recovery_read_model_rejects_missing_requirement": [
                    "recovery_read_model_rejects_missing_requirement"
                ],
                "recovery_read_model_rejects_duplicate_requirement_row": [
                    "recovery_read_model_rejects_duplicate_requirement_row"
                ],
                "recovery_read_model_rejects_missing_delta_reject_log": [
                    "recovery_read_model_rejects_missing_delta_reject_log"
                ],
                "recovery_read_model_rejects_witness_projection_drift": [
                    "recovery_read_model_rejects_witness_projection_drift"
                ],
                "recovery_read_model_rejects_evidence_ref_count_drift": [
                    "recovery_read_model_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_writer_identity_witness",
            [
                "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
                "validate_universal_symbol_receipt_store_writer_identity_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_operator_approval_witness.schema.json",
                "examples/universal_symbol_receipt_store_operator_approval_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_duty_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_duty_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_operator_approval_witness.py",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "scripts/validate_universal_symbol_receipt_store_writer_duty_scope_witness.py",
                "scripts/validate_universal_symbol_receipt_store_writer_identity_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store writer identity witness defines unique identity, operator approval, tenant scope, duty scope, schema-manifest, write-path boundary, lease/idempotency, and recovery requirements while denying writer identity registration, writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_writer_identity_witness_validates",
                "writer_identity_witness_rejects_registration_authority_drift",
                "writer_identity_witness_rejects_missing_requirement",
                "writer_identity_witness_rejects_missing_delta_reject",
                "writer_identity_witness_rejects_identity_constraint_drift",
                "writer_identity_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_writer_identity_witness_validates": [
                    "foundation_universal_symbol_receipt_store_writer_identity_witness_validates"
                ],
                "writer_identity_witness_rejects_registration_authority_drift": [
                    "writer_identity_witness_rejects_registration_authority_drift"
                ],
                "writer_identity_witness_rejects_missing_requirement": [
                    "writer_identity_witness_rejects_missing_requirement"
                ],
                "writer_identity_witness_rejects_missing_delta_reject": [
                    "writer_identity_witness_rejects_missing_delta_reject"
                ],
                "writer_identity_witness_rejects_identity_constraint_drift": [
                    "writer_identity_witness_rejects_identity_constraint_drift"
                ],
                "writer_identity_witness_rejects_evidence_ref_count_drift": [
                    "writer_identity_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_writer_registration_witness",
            [
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "validate_universal_symbol_receipt_store_writer_registration_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "scripts/validate_universal_symbol_receipt_store_writer_registration_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store writer registration witness defines writer identity, operator approval, append audit, write-path, idempotency, recovery, receipt-schema, and tenant-scope requirements while denying writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_writer_registration_witness_validates",
                "writer_registration_witness_rejects_append_authority_drift",
                "writer_registration_witness_rejects_missing_requirement",
                "writer_registration_witness_rejects_writer_identity_constraint_drift",
                "writer_registration_witness_rejects_evidence_ref_count_drift",
                "writer_registration_witness_rejects_writer_authority_drift",
                "writer_registration_witness_rejects_missing_delta_reject",
                "writer_registration_witness_rejects_scope_constraint_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_writer_registration_witness_validates": [
                    "foundation_universal_symbol_receipt_store_writer_registration_witness_validates"
                ],
                "writer_registration_witness_rejects_append_authority_drift": [
                    "writer_registration_witness_rejects_append_authority_drift"
                ],
                "writer_registration_witness_rejects_missing_requirement": [
                    "writer_registration_witness_rejects_missing_requirement"
                ],
                "writer_registration_witness_rejects_writer_identity_constraint_drift": [
                    "writer_registration_witness_rejects_writer_identity_constraint_drift"
                ],
                "writer_registration_witness_rejects_evidence_ref_count_drift": [
                    "writer_registration_witness_rejects_evidence_ref_count_drift"
                ],
                "writer_registration_witness_rejects_writer_authority_drift": [
                    "writer_registration_witness_rejects_writer_authority_drift"
                ],
                "writer_registration_witness_rejects_missing_delta_reject": [
                    "writer_registration_witness_rejects_missing_delta_reject"
                ],
                "writer_registration_witness_rejects_scope_constraint_drift": [
                    "writer_registration_witness_rejects_scope_constraint_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_path_custody_witness",
            [
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "validate_universal_symbol_receipt_store_path_custody_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_path_custody_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_custody_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_durability_replay_witness.schema.json",
                "examples/universal_symbol_receipt_store_durability_replay_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_identity_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_identity_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_path_confinement_witness.py",
                "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py",
                "scripts/validate_universal_symbol_receipt_store_durability_replay_witness.py",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "scripts/validate_universal_symbol_receipt_store_path_custody_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store path custody witness defines repository-relative custody, confinement, append-only, digest-only, idempotency, replay, recovery, and tenant/actor requirements while denying path custody registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_path_custody_witness_validates",
                "path_custody_witness_rejects_write_path_authority_drift",
                "path_custody_witness_rejects_missing_requirement",
                "path_custody_witness_rejects_missing_delta_reject",
                "path_custody_witness_rejects_constraint_drift",
                "path_custody_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_path_custody_witness_validates": [
                    "foundation_universal_symbol_receipt_store_path_custody_witness_validates"
                ],
                "path_custody_witness_rejects_write_path_authority_drift": [
                    "path_custody_witness_rejects_write_path_authority_drift"
                ],
                "path_custody_witness_rejects_missing_requirement": [
                    "path_custody_witness_rejects_missing_requirement"
                ],
                "path_custody_witness_rejects_missing_delta_reject": [
                    "path_custody_witness_rejects_missing_delta_reject"
                ],
                "path_custody_witness_rejects_constraint_drift": [
                    "path_custody_witness_rejects_constraint_drift"
                ],
                "path_custody_witness_rejects_evidence_ref_count_drift": [
                    "path_custody_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "universal_symbol_receipt_store_write_path_witness",
            [
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "validate_universal_symbol_receipt_store_write_path_witness",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/universal_symbol_receipt_store_write_path_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_path_confinement_witness.schema.json",
                "examples/universal_symbol_receipt_store_path_confinement_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_write_path_idempotency_witness.schema.json",
                "examples/universal_symbol_receipt_store_write_path_idempotency_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_tenant_scope_witness.schema.json",
                "examples/universal_symbol_receipt_store_tenant_scope_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_writer_registration_witness.schema.json",
                "examples/universal_symbol_receipt_store_writer_registration_witness.foundation.json",
                "schemas/universal_symbol_append_audit_witness.schema.json",
                "examples/universal_symbol_append_audit_witness.foundation.json",
                "schemas/universal_symbol_receipt_store_authority_witness.schema.json",
                "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
                "schemas/universal_symbol_adapter_receipt_persistence_policy.schema.json",
                "examples/universal_symbol_adapter_receipt_persistence_policy.foundation.json",
                "schemas/universal_symbol_runtime_admission_policy.schema.json",
                "schemas/universal_symbol.schema.json",
                "docs/91_universal_symbol_kernel.md",
                "docs/92_universal_symbol_kernel_audit.md",
                "scripts/validate_universal_symbol_receipt_store_path_confinement_witness.py",
                "scripts/validate_universal_symbol_receipt_store_write_path_idempotency_witness.py",
                "scripts/validate_universal_symbol_receipt_store_tenant_scope_witness.py",
                "scripts/validate_universal_symbol_receipt_store_write_path_witness.py",
                "tests/test_validate_universal_symbol_kernel.py",
                "scripts/proof_coverage_matrix.py",
                "tests/test_proof_coverage_matrix.py",
            ],
            "UniversalSymbol receipt-store write-path witness defines writer registration, custody, confinement, append-only, digest-only, idempotency, replay, recovery, tenant-actor, and operator approval requirements while denying writer registration, write-path registration, receipt append, raw payload storage, raw secret storage, runtime dispatch, connector calls, mutation, and terminal closure.",
            [
                "foundation_universal_symbol_receipt_store_write_path_witness_validates",
                "write_path_witness_rejects_append_authority_drift",
                "write_path_witness_rejects_missing_requirement",
                "write_path_witness_rejects_path_authority_drift",
                "write_path_witness_rejects_missing_delta_reject",
                "write_path_witness_rejects_constraint_drift",
                "write_path_witness_rejects_evidence_ref_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "foundation_universal_symbol_receipt_store_write_path_witness_validates": [
                    "foundation_universal_symbol_receipt_store_write_path_witness_validates"
                ],
                "write_path_witness_rejects_append_authority_drift": [
                    "write_path_witness_rejects_append_authority_drift"
                ],
                "write_path_witness_rejects_missing_requirement": [
                    "write_path_witness_rejects_missing_requirement"
                ],
                "write_path_witness_rejects_path_authority_drift": [
                    "write_path_witness_rejects_path_authority_drift"
                ],
                "write_path_witness_rejects_missing_delta_reject": [
                    "write_path_witness_rejects_missing_delta_reject"
                ],
                "write_path_witness_rejects_constraint_drift": [
                    "write_path_witness_rejects_constraint_drift"
                ],
                "write_path_witness_rejects_evidence_ref_count_drift": [
                    "write_path_witness_rejects_evidence_ref_count_drift"
                ],
            },
        ),
        _surface(
            "component_autopsy",
            ["/api/v1/components/{component_id}/autopsy"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_autopsy.py",
                "mcoi/mcoi_runtime/app/routers/components.py",
                "schemas/component_autopsy.schema.json",
                "examples/component_autopsy.nested_mind_bridge.json",
                "scripts/validate_component_autopsy.py",
                "mcoi/tests/test_component_autopsy_route.py",
                "tests/test_validate_component_autopsy.py",
            ],
            "Component Harness autopsy exposes component blockers, evidence, missing evidence, forbidden actions, and next transition previews without granting execution, connector, mutation, external send, file write, or terminal closure authority.",
            [
                "component_autopsy_explains_missing_evidence",
                "component_autopsy_route_is_read_only",
                "component_autopsy_rejects_unknown_component",
                "component_autopsy_schema_valid",
                "component_autopsy_blocks_live_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_autopsy_explains_missing_evidence": [
                    "component_autopsy_builds_nested_mind_blocker_view",
                    "component_autopsy_example_matches_runtime_projection",
                ],
                "component_autopsy_route_is_read_only": [
                    "component_autopsy_route_is_read_only",
                    "foundation_component_autopsies_keep_live_authority_false",
                ],
                "component_autopsy_rejects_unknown_component": [
                    "component_autopsy_route_rejects_unknown_component",
                    "component_autopsy_rejects_unknown_component",
                ],
                "component_autopsy_schema_valid": [
                    "component_autopsy_schema_valid_and_write",
                ],
                "component_autopsy_blocks_live_authority_drift": [
                    "component_autopsy_rejects_live_authority_and_missing_evidence_drift",
                ],
            },
        ),
        _surface(
            "component_request_simulator",
            ["/api/v1/components/simulate"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_request_simulator.py",
                "mcoi/mcoi_runtime/app/routers/components.py",
                "schemas/component_request_simulation.schema.json",
                "examples/component_request_simulation.foundation.json",
                "scripts/validate_component_request_simulation.py",
                "mcoi/tests/test_component_request_simulator.py",
                "tests/test_validate_component_request_simulation.py",
            ],
            "Component Harness request simulator predicts component path, blocked actions, approval need, receipts, and missing evidence without granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_request_simulator_predicts_send_email_blocked",
                "component_request_simulator_routes_deep_analysis_read_only",
                "component_request_simulator_route_is_preview_only",
                "component_request_simulation_schema_valid",
                "component_request_simulation_example_matches_runtime_projection",
            ],
            runtime_witness_anchor_aliases={
                "component_request_simulator_predicts_send_email_blocked": [
                    "component_request_simulator_predicts_send_email_blocked",
                ],
                "component_request_simulator_routes_deep_analysis_read_only": [
                    "component_request_simulator_routes_deep_analysis_read_only",
                ],
                "component_request_simulator_route_is_preview_only": [
                    "component_request_simulator_route_is_preview_only",
                ],
                "component_request_simulation_schema_valid": [
                    "component_request_simulation_schema_valid",
                ],
                "component_request_simulation_example_matches_runtime_projection": [
                    "component_request_simulation_example_matches_runtime_projection",
                ],
            },
        ),
        _surface(
            "component_bundle_compiler",
            ["component_bundle_compilation"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_bundle_compiler.py",
                "schemas/component_bundle_compilation.schema.json",
                "examples/component_bundle_compilation.personal_assistant_v0.json",
                "scripts/validate_component_bundle_compiler.py",
                "mcoi/tests/test_component_bundle_compiler.py",
                "tests/test_validate_component_bundle_compiler.py",
            ],
            "Component Harness bundle compiler joins registry bundles, component read-model posture, and request simulation evidence into preview-only product bundle reports without granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_bundle_compiler_compiles_personal_assistant_v0_preview",
                "component_bundle_compiler_compiles_all_foundation_bundles",
                "component_bundle_compilation_schema_valid",
                "component_bundle_compilation_example_matches_runtime_projection",
                "component_bundle_compiler_rejects_live_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_bundle_compiler_compiles_personal_assistant_v0_preview": [
                    "component_bundle_compiler_compiles_personal_assistant_v0_preview",
                ],
                "component_bundle_compiler_compiles_all_foundation_bundles": [
                    "component_bundle_compiler_compiles_all_foundation_bundles",
                ],
                "component_bundle_compilation_schema_valid": [
                    "component_bundle_compilation_schema_valid",
                ],
                "component_bundle_compilation_example_matches_runtime_projection": [
                    "component_bundle_compilation_example_matches_runtime_projection",
                ],
                "component_bundle_compiler_rejects_live_authority_drift": [
                    "component_bundle_compiler_rejects_live_authority_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_ownership",
            ["component_route_family_ownership"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_ownership.py",
                "schemas/component_route_family_ownership.schema.json",
                "examples/component_route_family_ownership.foundation.json",
                "scripts/validate_component_route_family_ownership.py",
                "tests/test_validate_component_route_family_ownership.py",
            ],
            "Component Harness route-family ownership readiness separates selected-bound route families from blocked promotions and requires proof, lifecycle, route-binding, and authority evidence before ownership promotion without granting execution or terminal closure authority.",
            [
                "component_route_family_ownership_schema_valid",
                "component_route_family_ownership_example_matches_runtime_projection",
                "component_route_family_ownership_blocks_authority_drift",
                "component_route_family_ownership_blocks_platform_promotion_overclaim",
                "component_route_family_ownership_reports_blocked_promotions",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_ownership_schema_valid": [
                    "component_route_family_ownership_schema_valid_and_write",
                ],
                "component_route_family_ownership_example_matches_runtime_projection": [
                    "component_route_family_ownership_example_matches_runtime_projection",
                ],
                "component_route_family_ownership_blocks_authority_drift": [
                    "component_route_family_ownership_rejects_authority_and_summary_drift",
                ],
                "component_route_family_ownership_blocks_platform_promotion_overclaim": [
                    "component_route_family_ownership_rejects_platform_promotion_overclaim",
                ],
                "component_route_family_ownership_reports_blocked_promotions": [
                    "component_route_family_ownership_schema_valid_and_write",
                    "component_route_family_ownership_example_matches_runtime_projection",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_preflight",
            ["component_route_family_promotion_preflight"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_preflight.py",
                "schemas/component_route_family_promotion_preflight.schema.json",
                "examples/component_route_family_promotion_preflight.governed_connector_framework.json",
                "scripts/validate_component_route_family_promotion_preflight.py",
                "tests/test_validate_component_route_family_promotion_preflight.py",
            ],
            "Component Harness route-family promotion preflight blocks governed connector framework promotion until product-specific route ownership, lifecycle, and authority witnesses exist without granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_preflight_schema_valid",
                "component_route_family_promotion_preflight_example_matches_runtime_projection",
                "component_route_family_promotion_preflight_blocks_authority_overclaim",
                "component_route_family_promotion_preflight_rejects_gate_drift",
                "component_route_family_promotion_preflight_rejects_selected_bound_target",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_preflight_schema_valid": [
                    "component_route_family_promotion_preflight_schema_valid_and_write",
                ],
                "component_route_family_promotion_preflight_example_matches_runtime_projection": [
                    "component_route_family_promotion_preflight_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_preflight_blocks_authority_overclaim": [
                    "component_route_family_promotion_preflight_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_preflight_rejects_gate_drift": [
                    "component_route_family_promotion_preflight_rejects_gate_drift",
                ],
                "component_route_family_promotion_preflight_rejects_selected_bound_target": [
                    "component_route_family_promotion_preflight_rejects_selected_bound_target",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_witness_requirements",
            ["component_route_family_promotion_witness_requirements"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_witness_requirements.py",
                "schemas/component_route_family_promotion_witness_requirements.schema.json",
                "examples/component_route_family_promotion_witness_requirements.governed_connector_framework.json",
                "scripts/validate_component_route_family_promotion_witness_requirements.py",
                "tests/test_validate_component_route_family_promotion_witness_requirements.py",
            ],
            "Component Harness promotion witness requirements compile the exact satisfied and missing witnesses for governed connector framework promotion without granting route ownership, execution, connector action, or terminal closure authority.",
            [
                "component_route_family_promotion_witness_requirements_schema_valid",
                "component_route_family_promotion_witness_requirements_example_matches_runtime_projection",
                "component_route_family_promotion_witness_requirements_rejects_authority_overclaim",
                "component_route_family_promotion_witness_requirements_rejects_missing_requirement",
                "component_route_family_promotion_witness_requirements_rejects_blocker_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_witness_requirements_schema_valid": [
                    "component_route_family_promotion_witness_requirements_schema_valid_and_write",
                ],
                "component_route_family_promotion_witness_requirements_example_matches_runtime_projection": [
                    "component_route_family_promotion_witness_requirements_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_witness_requirements_rejects_authority_overclaim": [
                    "component_route_family_promotion_witness_requirements_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_witness_requirements_rejects_missing_requirement": [
                    "component_route_family_promotion_witness_requirements_rejects_missing_requirement",
                ],
                "component_route_family_promotion_witness_requirements_rejects_blocker_drift": [
                    "component_route_family_promotion_witness_requirements_rejects_blocker_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_witness_evidence",
            ["component_route_family_promotion_witness_evidence"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_witness_evidence.py",
                "schemas/component_route_family_promotion_witness_evidence.schema.json",
                "examples/component_route_family_promotion_witness_evidence.governed_connector_framework.json",
                "scripts/validate_component_route_family_promotion_witness_evidence.py",
                "tests/test_validate_component_route_family_promotion_witness_evidence.py",
            ],
            "Component Harness promotion witness evidence records concrete denials for all hard promotion blockers without mutating router inventory or granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_witness_evidence_schema_valid",
                "component_route_family_promotion_witness_evidence_example_matches_runtime_projection",
                "component_route_family_promotion_witness_evidence_rejects_authority_overclaim",
                "component_route_family_promotion_witness_evidence_rejects_missing_route_binding_witness",
                "component_route_family_promotion_witness_evidence_rejects_satisfied_product_ownership_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_witness_evidence_schema_valid": [
                    "component_route_family_promotion_witness_evidence_schema_valid_and_write",
                ],
                "component_route_family_promotion_witness_evidence_example_matches_runtime_projection": [
                    "component_route_family_promotion_witness_evidence_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_witness_evidence_rejects_authority_overclaim": [
                    "component_route_family_promotion_witness_evidence_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_witness_evidence_rejects_missing_route_binding_witness": [
                    "component_route_family_promotion_witness_evidence_rejects_missing_route_binding_witness",
                ],
                "component_route_family_promotion_witness_evidence_rejects_satisfied_product_ownership_drift": [
                    "component_route_family_promotion_witness_evidence_rejects_satisfied_product_ownership_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_approval_candidates",
            ["component_route_family_promotion_approval_candidates"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_approval_candidates.py",
                "schemas/component_route_family_promotion_approval_candidates.schema.json",
                "examples/component_route_family_promotion_approval_candidates.governed_connector_framework.json",
                "scripts/validate_component_route_family_promotion_approval_candidates.py",
                "tests/test_validate_component_route_family_promotion_approval_candidates.py",
            ],
            "Component Harness promotion approval candidates describe draft-only route-binding, lifecycle, authority-upgrade, and product-specific ownership candidates without approving promotion, mutating router inventory, or granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_approval_candidates_schema_valid",
                "component_route_family_promotion_approval_candidates_example_matches_runtime_projection",
                "component_route_family_promotion_approval_candidates_rejects_authority_overclaim",
                "component_route_family_promotion_approval_candidates_rejects_missing_candidate",
                "component_route_family_promotion_approval_candidates_rejects_approval_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_approval_candidates_schema_valid": [
                    "component_route_family_promotion_approval_candidates_schema_valid_and_write",
                ],
                "component_route_family_promotion_approval_candidates_example_matches_runtime_projection": [
                    "component_route_family_promotion_approval_candidates_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_approval_candidates_rejects_authority_overclaim": [
                    "component_route_family_promotion_approval_candidates_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_approval_candidates_rejects_missing_candidate": [
                    "component_route_family_promotion_approval_candidates_rejects_missing_candidate",
                ],
                "component_route_family_promotion_approval_candidates_rejects_approval_drift": [
                    "component_route_family_promotion_approval_candidates_rejects_approval_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_approval_intake",
            ["component_route_family_promotion_approval_intake"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_approval_intake.py",
                "schemas/component_route_family_promotion_approval_intake.schema.json",
                "examples/component_route_family_promotion_approval_intake.governed_connector_framework.json",
                "scripts/validate_component_route_family_promotion_approval_intake.py",
                "tests/test_validate_component_route_family_promotion_approval_intake.py",
            ],
            "Component Harness promotion approval intake exposes open operator evidence requests for blocked route-binding, lifecycle, authority-upgrade, and product-specific ownership gates without accepting evidence, approving promotion, mutating router inventory, or granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_approval_intake_schema_valid",
                "component_route_family_promotion_approval_intake_example_matches_runtime_projection",
                "component_route_family_promotion_approval_intake_rejects_authority_overclaim",
                "component_route_family_promotion_approval_intake_rejects_missing_request",
                "component_route_family_promotion_approval_intake_rejects_submission_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_approval_intake_schema_valid": [
                    "component_route_family_promotion_approval_intake_schema_valid_and_write",
                ],
                "component_route_family_promotion_approval_intake_example_matches_runtime_projection": [
                    "component_route_family_promotion_approval_intake_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_approval_intake_rejects_authority_overclaim": [
                    "component_route_family_promotion_approval_intake_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_approval_intake_rejects_missing_request": [
                    "component_route_family_promotion_approval_intake_rejects_missing_request",
                ],
                "component_route_family_promotion_approval_intake_rejects_submission_drift": [
                    "component_route_family_promotion_approval_intake_rejects_submission_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_submitted_evidence_verifier",
            ["component_route_family_promotion_submitted_evidence_verifier"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_submitted_evidence_verifier.py",
                "schemas/component_route_family_promotion_submitted_evidence_verifier.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_submitted_evidence_verifier.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_submitted_evidence_verifier.py",
                "tests/test_validate_component_route_family_promotion_submitted_evidence_verifier.py",
            ],
            "Component Harness submitted-evidence verifier records that all promotion intake requests are awaiting submitted evidence, not verified, and still blocked without approving promotion, mutating router inventory, or granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_submitted_evidence_verifier_schema_valid",
                "component_route_family_promotion_submitted_evidence_verifier_example_matches_runtime_projection",
                "component_route_family_promotion_submitted_evidence_verifier_rejects_authority_overclaim",
                "component_route_family_promotion_submitted_evidence_verifier_rejects_missing_request",
                "component_route_family_promotion_submitted_evidence_verifier_rejects_submission_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_submitted_evidence_verifier_schema_valid": [
                    "component_route_family_promotion_submitted_evidence_verifier_schema_valid_and_write",
                ],
                "component_route_family_promotion_submitted_evidence_verifier_example_matches_runtime_projection": [
                    "component_route_family_promotion_submitted_evidence_verifier_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_submitted_evidence_verifier_rejects_authority_overclaim": [
                    "component_route_family_promotion_submitted_evidence_verifier_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_submitted_evidence_verifier_rejects_missing_request": [
                    "component_route_family_promotion_submitted_evidence_verifier_rejects_missing_request",
                ],
                "component_route_family_promotion_submitted_evidence_verifier_rejects_submission_drift": [
                    "component_route_family_promotion_submitted_evidence_verifier_rejects_submission_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_submitted_evidence_records",
            ["component_route_family_promotion_submitted_evidence_records"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_submitted_evidence_records.py",
                "schemas/component_route_family_promotion_submitted_evidence_records.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_submitted_evidence_records.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_submitted_evidence_records.py",
                "tests/test_validate_component_route_family_promotion_submitted_evidence_records.py",
            ],
            "Component Harness submitted-evidence record envelopes define template-only payload requirements for blocked promotion verifier requests without accepting payloads, approving promotion, mutating router inventory, or granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_submitted_evidence_records_schema_valid",
                "component_route_family_promotion_submitted_evidence_records_example_matches_runtime_projection",
                "component_route_family_promotion_submitted_evidence_records_rejects_authority_overclaim",
                "component_route_family_promotion_submitted_evidence_records_rejects_missing_envelope",
                "component_route_family_promotion_submitted_evidence_records_rejects_payload_submission_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_submitted_evidence_records_schema_valid": [
                    "component_route_family_promotion_submitted_evidence_records_schema_valid_and_write",
                ],
                "component_route_family_promotion_submitted_evidence_records_example_matches_runtime_projection": [
                    "component_route_family_promotion_submitted_evidence_records_example_matches_runtime_projection",
                ],
                "component_route_family_promotion_submitted_evidence_records_rejects_authority_overclaim": [
                    "component_route_family_promotion_submitted_evidence_records_rejects_authority_overclaim",
                ],
                "component_route_family_promotion_submitted_evidence_records_rejects_missing_envelope": [
                    "component_route_family_promotion_submitted_evidence_records_rejects_missing_envelope",
                ],
                "component_route_family_promotion_submitted_evidence_records_rejects_payload_submission_drift": [
                    "component_route_family_promotion_submitted_evidence_records_rejects_payload_submission_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_submitted_evidence_payload_examples",
            ["component_route_family_promotion_submitted_evidence_payload_examples"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_submitted_evidence_payload_examples.py",
                "schemas/component_route_family_promotion_submitted_evidence_payload_examples.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_submitted_evidence_payload_examples.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_submitted_evidence_payload_examples.py",
                "tests/test_validate_component_route_family_promotion_submitted_evidence_payload_examples.py",
            ],
            "Component Harness submitted-evidence payload examples define concrete example payload values and acceptance-rule contracts for blocked promotion record envelopes without submitting evidence, applying rules, approving promotion, mutating router inventory, or granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_route_family_promotion_submitted_evidence_payload_examples_schema_valid",
                "component_route_family_promotion_submitted_evidence_payload_examples_match_runtime_projection",
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_authority_overclaim",
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_missing_payload",
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_submission_drift",
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_rule_application_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_submitted_evidence_payload_examples_schema_valid": [
                    "component_route_family_promotion_submitted_evidence_payload_examples_schema_valid_and_write",
                ],
                "component_route_family_promotion_submitted_evidence_payload_examples_match_runtime_projection": [
                    "component_route_family_promotion_submitted_evidence_payload_examples_match_runtime_projection",
                ],
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_authority_overclaim": [
                    "component_route_family_promotion_submitted_evidence_payload_examples_reject_authority_overclaim",
                ],
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_missing_payload": [
                    "component_route_family_promotion_submitted_evidence_payload_examples_reject_missing_payload",
                ],
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_submission_drift": [
                    "component_route_family_promotion_submitted_evidence_payload_examples_reject_submission_drift",
                ],
                "component_route_family_promotion_submitted_evidence_payload_examples_reject_rule_application_drift": [
                    "component_route_family_promotion_submitted_evidence_payload_examples_reject_rule_application_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_operator_submitted_evidence_records",
            ["component_route_family_promotion_operator_submitted_evidence_records"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_operator_submitted_evidence_records.py",
                "schemas/component_route_family_promotion_operator_submitted_evidence_records.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_operator_submitted_evidence_records.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_operator_submitted_evidence_records.py",
                "tests/test_validate_component_route_family_promotion_operator_submitted_evidence_records.py",
            ],
            "Component Harness operator-submitted evidence records apply defined acceptance rules to submitted-for-review promotion payload records while keeping promotion blocked and denying execution, connector, mutation, router-inventory, and terminal closure authority.",
            [
                "component_route_family_promotion_operator_submitted_evidence_records_schema_valid",
                "component_route_family_promotion_operator_submitted_evidence_records_match_runtime_projection",
                "component_route_family_promotion_operator_submitted_evidence_records_reject_authority_overclaim",
                "component_route_family_promotion_operator_submitted_evidence_records_reject_missing_record",
                "component_route_family_promotion_operator_submitted_evidence_records_reject_unapplied_rule_drift",
                "component_route_family_promotion_operator_submitted_evidence_records_reject_promotion_satisfaction_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_operator_submitted_evidence_records_schema_valid": [
                    "component_route_family_promotion_operator_submitted_evidence_records_schema_valid_and_write",
                ],
                "component_route_family_promotion_operator_submitted_evidence_records_match_runtime_projection": [
                    "component_route_family_promotion_operator_submitted_evidence_records_match_runtime_projection",
                ],
                "component_route_family_promotion_operator_submitted_evidence_records_reject_authority_overclaim": [
                    "component_route_family_promotion_operator_submitted_evidence_records_reject_authority_overclaim",
                ],
                "component_route_family_promotion_operator_submitted_evidence_records_reject_missing_record": [
                    "component_route_family_promotion_operator_submitted_evidence_records_reject_missing_record",
                ],
                "component_route_family_promotion_operator_submitted_evidence_records_reject_unapplied_rule_drift": [
                    "component_route_family_promotion_operator_submitted_evidence_records_reject_unapplied_rule_drift",
                ],
                "component_route_family_promotion_operator_submitted_evidence_records_reject_promotion_satisfaction_drift": [
                    "component_route_family_promotion_operator_submitted_evidence_records_reject_promotion_satisfaction_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_gate_satisfaction_evaluator",
            ["component_route_family_promotion_gate_satisfaction_evaluator"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_gate_satisfaction_evaluator.py",
                "schemas/component_route_family_promotion_gate_satisfaction_evaluator.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_gate_satisfaction_evaluator.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_gate_satisfaction_evaluator.py",
                "tests/test_validate_component_route_family_promotion_gate_satisfaction_evaluator.py",
            ],
            "Component Harness promotion gate-satisfaction evaluator consumes accepted record-only evidence to mark evidence gates satisfied while action gates, promotion approval, route mutation, execution, connector, mutation, and terminal-closure authority remain blocked.",
            [
                "component_route_family_promotion_gate_satisfaction_evaluator_schema_valid",
                "component_route_family_promotion_gate_satisfaction_evaluator_match_runtime_projection",
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_authority_overclaim",
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_missing_gate",
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_record_satisfaction_drift",
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_promotion_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_gate_satisfaction_evaluator_schema_valid": [
                    "component_route_family_promotion_gate_satisfaction_evaluator_schema_valid_and_write",
                ],
                "component_route_family_promotion_gate_satisfaction_evaluator_match_runtime_projection": [
                    "component_route_family_promotion_gate_satisfaction_evaluator_match_runtime_projection",
                ],
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_authority_overclaim": [
                    "component_route_family_promotion_gate_satisfaction_evaluator_reject_authority_overclaim",
                ],
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_missing_gate": [
                    "component_route_family_promotion_gate_satisfaction_evaluator_reject_missing_gate",
                ],
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_record_satisfaction_drift": [
                    "component_route_family_promotion_gate_satisfaction_evaluator_reject_record_satisfaction_drift",
                ],
                "component_route_family_promotion_gate_satisfaction_evaluator_reject_promotion_authority_drift": [
                    "component_route_family_promotion_gate_satisfaction_evaluator_reject_promotion_authority_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_authority_decision_report",
            ["component_route_family_promotion_authority_decision_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_authority_decision_report.py",
                "schemas/component_route_family_promotion_authority_decision_report.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_authority_decision_report.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_authority_decision_report.py",
                "tests/test_validate_component_route_family_promotion_authority_decision_report.py",
            ],
            "Component Harness promotion authority decision report consumes gate-satisfaction evidence and records four denial-only authority decisions while route binding, lifecycle transition, promotion approval, execution, connector, mutation, and terminal-closure authority remain blocked.",
            [
                "component_route_family_promotion_authority_decision_report_schema_valid",
                "component_route_family_promotion_authority_decision_report_match_runtime_projection",
                "component_route_family_promotion_authority_decision_report_reject_authority_grant_overclaim",
                "component_route_family_promotion_authority_decision_report_reject_missing_decision",
                "component_route_family_promotion_authority_decision_report_reject_record_satisfaction_drift",
                "component_route_family_promotion_authority_decision_report_reject_promotion_approval_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_authority_decision_report_schema_valid": [
                    "component_route_family_promotion_authority_decision_report_schema_valid_and_write",
                ],
                "component_route_family_promotion_authority_decision_report_match_runtime_projection": [
                    "component_route_family_promotion_authority_decision_report_match_runtime_projection",
                ],
                "component_route_family_promotion_authority_decision_report_reject_authority_grant_overclaim": [
                    "component_route_family_promotion_authority_decision_report_reject_authority_grant_overclaim",
                ],
                "component_route_family_promotion_authority_decision_report_reject_missing_decision": [
                    "component_route_family_promotion_authority_decision_report_reject_missing_decision",
                ],
                "component_route_family_promotion_authority_decision_report_reject_record_satisfaction_drift": [
                    "component_route_family_promotion_authority_decision_report_reject_record_satisfaction_drift",
                ],
                "component_route_family_promotion_authority_decision_report_reject_promotion_approval_drift": [
                    "component_route_family_promotion_authority_decision_report_reject_promotion_approval_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_route_binding_decision_report",
            ["component_route_family_promotion_route_binding_decision_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_route_binding_decision_report.py",
                "schemas/component_route_family_promotion_route_binding_decision_report.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_route_binding_decision_report.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_route_binding_decision_report.py",
                "tests/test_validate_component_route_family_promotion_route_binding_decision_report.py",
            ],
            "Component Harness promotion route-binding decision report consumes a denied authority decision and records one denial-only route-binding decision while router inventory mutation, selected-component binding, promotion approval, authority grants, execution, connector calls, and terminal closure remain blocked.",
            [
                "component_route_family_promotion_route_binding_decision_report_schema_valid",
                "component_route_family_promotion_route_binding_decision_report_match_runtime_projection",
                "component_route_family_promotion_route_binding_decision_report_reject_route_authorization_overclaim",
                "component_route_family_promotion_route_binding_decision_report_reject_missing_decision",
                "component_route_family_promotion_route_binding_decision_report_reject_record_satisfaction_drift",
                "component_route_family_promotion_route_binding_decision_report_reject_router_inventory_mutation_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_route_binding_decision_report_schema_valid": [
                    "component_route_family_promotion_route_binding_decision_report_schema_valid_and_write",
                ],
                "component_route_family_promotion_route_binding_decision_report_match_runtime_projection": [
                    "component_route_family_promotion_route_binding_decision_report_match_runtime_projection",
                ],
                "component_route_family_promotion_route_binding_decision_report_reject_route_authorization_overclaim": [
                    "component_route_family_promotion_route_binding_decision_report_reject_route_authorization_overclaim",
                ],
                "component_route_family_promotion_route_binding_decision_report_reject_missing_decision": [
                    "component_route_family_promotion_route_binding_decision_report_reject_missing_decision",
                ],
                "component_route_family_promotion_route_binding_decision_report_reject_record_satisfaction_drift": [
                    "component_route_family_promotion_route_binding_decision_report_reject_record_satisfaction_drift",
                ],
                "component_route_family_promotion_route_binding_decision_report_reject_router_inventory_mutation_drift": [
                    "component_route_family_promotion_route_binding_decision_report_reject_router_inventory_mutation_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_lifecycle_transition_decision_report",
            ["component_route_family_promotion_lifecycle_transition_decision_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_lifecycle_transition_decision_report.py",
                "schemas/component_route_family_promotion_lifecycle_transition_decision_report.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_lifecycle_transition_decision_report.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_lifecycle_transition_decision_report.py",
                "tests/test_validate_component_route_family_promotion_lifecycle_transition_decision_report.py",
            ],
            "Component Harness promotion lifecycle-transition decision report consumes a denied route-binding decision and records one denial-only lifecycle decision while lifecycle state change, lifecycle receipts, promotion approval, authority grants, execution, connector calls, and terminal closure remain blocked.",
            [
                "component_route_family_promotion_lifecycle_transition_decision_report_schema_valid",
                "component_route_family_promotion_lifecycle_transition_decision_report_match_runtime_projection",
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_state_change_overclaim",
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_missing_decision",
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_proof_drift",
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_lifecycle_receipt_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_lifecycle_transition_decision_report_schema_valid": [
                    "component_route_family_promotion_lifecycle_transition_decision_report_schema_valid_and_write",
                ],
                "component_route_family_promotion_lifecycle_transition_decision_report_match_runtime_projection": [
                    "component_route_family_promotion_lifecycle_transition_decision_report_match_runtime_projection",
                ],
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_state_change_overclaim": [
                    "component_route_family_promotion_lifecycle_transition_decision_report_reject_state_change_overclaim",
                ],
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_missing_decision": [
                    "component_route_family_promotion_lifecycle_transition_decision_report_reject_missing_decision",
                ],
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_proof_drift": [
                    "component_route_family_promotion_lifecycle_transition_decision_report_reject_proof_drift",
                ],
                "component_route_family_promotion_lifecycle_transition_decision_report_reject_lifecycle_receipt_drift": [
                    "component_route_family_promotion_lifecycle_transition_decision_report_reject_lifecycle_receipt_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_authority_upgrade_witness_decision_report",
            ["component_route_family_promotion_authority_upgrade_witness_decision_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_authority_upgrade_witness_decision_report.py",
                "schemas/component_route_family_promotion_authority_upgrade_witness_decision_report.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_authority_upgrade_witness_decision_report.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_authority_upgrade_witness_decision_report.py",
                "tests/test_validate_component_route_family_promotion_authority_upgrade_witness_decision_report.py",
            ],
            "Component Harness promotion authority-upgrade witness decision report consumes a denied lifecycle-transition decision and records one denial-only authority-upgrade decision while authority grants, witness emission, authority-envelope mutation, execution, connector calls, and terminal closure remain blocked.",
            [
                "component_route_family_promotion_authority_upgrade_witness_decision_report_schema_valid",
                "component_route_family_promotion_authority_upgrade_witness_decision_report_match_runtime_projection",
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_authority_overclaim",
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_missing_decision",
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_proof_drift",
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_witness_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_authority_upgrade_witness_decision_report_schema_valid": [
                    "component_route_family_promotion_authority_upgrade_witness_decision_report_schema_valid_and_write",
                ],
                "component_route_family_promotion_authority_upgrade_witness_decision_report_match_runtime_projection": [
                    "component_route_family_promotion_authority_upgrade_witness_decision_report_match_runtime_projection",
                ],
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_authority_overclaim": [
                    "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_authority_overclaim",
                ],
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_missing_decision": [
                    "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_missing_decision",
                ],
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_proof_drift": [
                    "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_proof_drift",
                ],
                "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_witness_drift": [
                    "component_route_family_promotion_authority_upgrade_witness_decision_report_reject_witness_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_product_ownership_decision_report",
            ["component_route_family_promotion_product_ownership_decision_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_product_ownership_decision_report.py",
                "schemas/component_route_family_promotion_product_ownership_decision_report.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_product_ownership_decision_report.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_product_ownership_decision_report.py",
                "tests/test_validate_component_route_family_promotion_product_ownership_decision_report.py",
            ],
            "Component Harness promotion product-ownership decision report consumes a denied authority-upgrade decision and records one denial-only product-specific ownership decision while product ownership, product bundle binding, authority grants, execution, connector calls, router mutation, and terminal closure remain blocked.",
            [
                "component_route_family_promotion_product_ownership_decision_report_schema_valid",
                "component_route_family_promotion_product_ownership_decision_report_match_runtime_projection",
                "component_route_family_promotion_product_ownership_decision_report_reject_ownership_overclaim",
                "component_route_family_promotion_product_ownership_decision_report_reject_missing_decision",
                "component_route_family_promotion_product_ownership_decision_report_reject_source_ref_drift",
                "component_route_family_promotion_product_ownership_decision_report_reject_witness_binding_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_product_ownership_decision_report_schema_valid": [
                    "component_route_family_promotion_product_ownership_decision_report_schema_valid_and_write",
                ],
                "component_route_family_promotion_product_ownership_decision_report_match_runtime_projection": [
                    "component_route_family_promotion_product_ownership_decision_report_match_runtime_projection",
                ],
                "component_route_family_promotion_product_ownership_decision_report_reject_ownership_overclaim": [
                    "component_route_family_promotion_product_ownership_decision_report_reject_ownership_overclaim",
                ],
                "component_route_family_promotion_product_ownership_decision_report_reject_missing_decision": [
                    "component_route_family_promotion_product_ownership_decision_report_reject_missing_decision",
                ],
                "component_route_family_promotion_product_ownership_decision_report_reject_source_ref_drift": [
                    "component_route_family_promotion_product_ownership_decision_report_reject_source_ref_drift",
                ],
                "component_route_family_promotion_product_ownership_decision_report_reject_witness_binding_drift": [
                    "component_route_family_promotion_product_ownership_decision_report_reject_witness_binding_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_terminal_closure_denial_report",
            ["component_route_family_promotion_terminal_closure_denial_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_terminal_closure_denial_report.py",
                "schemas/component_route_family_promotion_terminal_closure_denial_report.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_terminal_closure_denial_report.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_terminal_closure_denial_report.py",
                "tests/test_validate_component_route_family_promotion_terminal_closure_denial_report.py",
            ],
            "Component Harness promotion terminal-closure denial report consumes a denied product-ownership decision and records one denial-only terminal-closure decision while terminal certificates, closure claims, promotion approval, authority grants, execution, connector calls, and router mutation remain blocked.",
            [
                "component_route_family_promotion_terminal_closure_denial_report_schema_valid",
                "component_route_family_promotion_terminal_closure_denial_report_match_runtime_projection",
                "component_route_family_promotion_terminal_closure_denial_report_reject_closure_overclaim",
                "component_route_family_promotion_terminal_closure_denial_report_reject_missing_decision",
                "component_route_family_promotion_terminal_closure_denial_report_reject_source_ref_drift",
                "component_route_family_promotion_terminal_closure_denial_report_reject_certificate_witness_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_terminal_closure_denial_report_schema_valid": [
                    "component_route_family_promotion_terminal_closure_denial_report_schema_valid_and_write",
                ],
                "component_route_family_promotion_terminal_closure_denial_report_match_runtime_projection": [
                    "component_route_family_promotion_terminal_closure_denial_report_match_runtime_projection",
                ],
                "component_route_family_promotion_terminal_closure_denial_report_reject_closure_overclaim": [
                    "component_route_family_promotion_terminal_closure_denial_report_reject_closure_overclaim",
                ],
                "component_route_family_promotion_terminal_closure_denial_report_reject_missing_decision": [
                    "component_route_family_promotion_terminal_closure_denial_report_reject_missing_decision",
                ],
                "component_route_family_promotion_terminal_closure_denial_report_reject_source_ref_drift": [
                    "component_route_family_promotion_terminal_closure_denial_report_reject_source_ref_drift",
                ],
                "component_route_family_promotion_terminal_closure_denial_report_reject_certificate_witness_drift": [
                    "component_route_family_promotion_terminal_closure_denial_report_reject_certificate_witness_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_missing_evidence_ledger",
            ["component_route_family_promotion_missing_evidence_ledger"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_missing_evidence_ledger.py",
                "schemas/component_route_family_promotion_missing_evidence_ledger.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_missing_evidence_ledger.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_missing_evidence_ledger.py",
                "tests/test_validate_component_route_family_promotion_missing_evidence_ledger.py",
            ],
            "Component Harness promotion missing-evidence ledger consumes terminal-closure denial and records six missing promotion blockers without creating witnesses, terminal certificates, authority grants, promotion approvals, execution, connector calls, or router mutation.",
            [
                "component_route_family_promotion_missing_evidence_ledger_schema_valid",
                "component_route_family_promotion_missing_evidence_ledger_match_runtime_projection",
                "component_route_family_promotion_missing_evidence_ledger_reject_evidence_overclaim",
                "component_route_family_promotion_missing_evidence_ledger_reject_missing_record",
                "component_route_family_promotion_missing_evidence_ledger_reject_source_ref_drift",
                "component_route_family_promotion_missing_evidence_ledger_reject_witness_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_missing_evidence_ledger_schema_valid": [
                    "component_route_family_promotion_missing_evidence_ledger_schema_valid_and_write",
                ],
                "component_route_family_promotion_missing_evidence_ledger_match_runtime_projection": [
                    "component_route_family_promotion_missing_evidence_ledger_match_runtime_projection",
                ],
                "component_route_family_promotion_missing_evidence_ledger_reject_evidence_overclaim": [
                    "component_route_family_promotion_missing_evidence_ledger_reject_evidence_overclaim",
                ],
                "component_route_family_promotion_missing_evidence_ledger_reject_missing_record": [
                    "component_route_family_promotion_missing_evidence_ledger_reject_missing_record",
                ],
                "component_route_family_promotion_missing_evidence_ledger_reject_source_ref_drift": [
                    "component_route_family_promotion_missing_evidence_ledger_reject_source_ref_drift",
                ],
                "component_route_family_promotion_missing_evidence_ledger_reject_witness_drift": [
                    "component_route_family_promotion_missing_evidence_ledger_reject_witness_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_candidate",
            ["component_route_family_promotion_router_inventory_delta_candidate"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_candidate.py",
                "schemas/component_route_family_promotion_router_inventory_delta_candidate.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_candidate.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_router_inventory_delta_candidate.py",
                "tests/test_validate_component_route_family_promotion_router_inventory_delta_candidate.py",
            ],
            "Component Harness promotion router-inventory delta candidate consumes the missing-evidence ledger and defines a dry-run selected-component delta path without applying a delta, mutating router inventory, creating evidence, granting authority, approving promotion, or claiming closure.",
            [
                "component_route_family_promotion_router_inventory_delta_candidate_schema_valid",
                "component_route_family_promotion_router_inventory_delta_candidate_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_candidate_reject_delta_overclaim",
                "component_route_family_promotion_router_inventory_delta_candidate_reject_missing_candidate",
                "component_route_family_promotion_router_inventory_delta_candidate_reject_source_ref_drift",
                "component_route_family_promotion_router_inventory_delta_candidate_reject_witness_mutation_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_candidate_schema_valid": [
                    "component_route_family_promotion_router_inventory_delta_candidate_schema_valid_and_write",
                ],
                "component_route_family_promotion_router_inventory_delta_candidate_match_runtime_projection": [
                    "component_route_family_promotion_router_inventory_delta_candidate_match_runtime_projection",
                ],
                "component_route_family_promotion_router_inventory_delta_candidate_reject_delta_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_candidate_reject_delta_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_candidate_reject_missing_candidate": [
                    "component_route_family_promotion_router_inventory_delta_candidate_reject_missing_candidate",
                ],
                "component_route_family_promotion_router_inventory_delta_candidate_reject_source_ref_drift": [
                    "component_route_family_promotion_router_inventory_delta_candidate_reject_source_ref_drift",
                ],
                "component_route_family_promotion_router_inventory_delta_candidate_reject_witness_mutation_drift": [
                    "component_route_family_promotion_router_inventory_delta_candidate_reject_witness_mutation_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_witness_requirements",
            ["component_route_family_promotion_router_inventory_delta_witness_requirements"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_requirements.py",
                "schemas/component_route_family_promotion_router_inventory_delta_witness_requirements.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_witness_requirements.governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_requirements.py",
                "tests/test_validate_component_route_family_promotion_router_inventory_delta_witness_requirements.py",
            ],
            "Component Harness promotion router-inventory delta witness requirements consume the dry-run candidate and declare six unmet requirements before a selected-component router-inventory delta witness can be minted, without applying a delta, mutating router inventory, granting authority, approving promotion, or claiming closure.",
            [
                "component_route_family_promotion_router_inventory_delta_witness_requirements_schema_valid",
                "component_route_family_promotion_router_inventory_delta_witness_requirements_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_witness_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_missing_requirement",
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_source_ref_drift",
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_mutation_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_witness_requirements_schema_valid": [
                    "component_route_family_promotion_router_inventory_delta_witness_requirements_schema_valid_and_write",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_requirements_match_runtime_projection": [
                    "component_route_family_promotion_router_inventory_delta_witness_requirements_match_runtime_projection",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_witness_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_witness_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_missing_requirement": [
                    "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_missing_requirement",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_source_ref_drift": [
                    "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_source_ref_drift",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_mutation_authority_drift": [
                    "component_route_family_promotion_router_inventory_delta_witness_requirements_reject_mutation_authority_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_witness_minting_preflight",
            ["component_route_family_promotion_router_inventory_delta_witness_minting_preflight"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                (
                    "mcoi/mcoi_runtime/app/"
                    "component_route_family_promotion_router_inventory_delta_witness_minting_preflight.py"
                ),
                (
                    "schemas/"
                    "component_route_family_promotion_router_inventory_delta_witness_minting_preflight.schema.json"
                ),
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_witness_minting_preflight."
                    "governed_connector_framework.json"
                ),
                (
                    "scripts/"
                    "validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight.py"
                ),
                (
                    "tests/"
                    "test_validate_component_route_family_promotion_router_inventory_delta_witness_minting_preflight.py"
                ),
            ],
            "Component Harness promotion router-inventory delta witness minting preflight consumes unmet witness requirements and blocks witness minting while preserving zero applied deltas, zero router inventory mutations, zero selected-component bindings, zero authority grants, zero promotion approvals, and zero terminal closure claims.",
            [
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_schema_valid",
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_witness_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_missing_check",
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_source_ref_drift",
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_mutation_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_schema_valid": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_"
                        "schema_valid_and_write"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_match_runtime_projection": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_"
                        "match_runtime_projection"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_witness_overclaim": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_"
                        "reject_witness_overclaim"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_missing_check": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_"
                        "reject_missing_check"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_source_ref_drift": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_"
                        "reject_source_ref_drift"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_reject_mutation_authority_drift": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_preflight_"
                        "reject_mutation_authority_drift"
                    ),
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report",
            ["component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                (
                    "mcoi/mcoi_runtime/app/"
                    "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.py"
                ),
                (
                    "schemas/"
                    "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.schema.json"
                ),
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report."
                    "governed_connector_framework.json"
                ),
                (
                    "scripts/"
                    "validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.py"
                ),
                (
                    "tests/"
                    "test_validate_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report.py"
                ),
            ],
            "Component Harness promotion router-inventory delta witness minting denial report consumes the blocked minting preflight and records a denied witness-minting decision without minting a witness, applying a delta, mutating router inventory, granting authority, approving promotion, or claiming closure.",
            [
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_schema_valid",
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_witness_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_missing_decision",
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_source_ref_drift",
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_mutation_authority_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_schema_valid": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_"
                        "schema_valid_and_write"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_match_runtime_projection": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_"
                        "match_runtime_projection"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_witness_overclaim": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_"
                        "reject_witness_overclaim"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_missing_decision": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_"
                        "reject_missing_decision"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_source_ref_drift": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_"
                        "reject_source_ref_drift"
                    ),
                ],
                "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_reject_mutation_authority_drift": [
                    (
                        "component_route_family_promotion_router_inventory_delta_witness_minting_denial_report_"
                        "reject_mutation_authority_drift"
                    ),
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_witness_remediation_plan",
            ["component_route_family_promotion_router_inventory_delta_witness_remediation_plan"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_remediation_plan.py",
                "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_plan.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan."
                    "governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan.py",
                "tests/test_validate_component_route_family_promotion_router_inventory_delta_witness_remediation_plan.py",
            ],
            "Component Harness promotion router-inventory delta witness remediation plan consumes the minting denial report and declares six plan-only evidence obligations without submitting evidence, accepting evidence, authorizing witness minting, minting a witness, applying a delta, mutating router inventory, or granting authority.",
            [
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_schema_valid",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_evidence_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_missing_step",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_source_ref_drift",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_mutation_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_schema_valid": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_schema_valid_and_write",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_match_runtime_projection": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_match_runtime_projection",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_evidence_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_evidence_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_missing_step": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_missing_step",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_source_ref_drift": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_source_ref_drift",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_mutation_drift": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_plan_reject_mutation_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request",
            ["component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.py",
                "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request."
                    "governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.py",
                "tests/test_validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request.py",
            ],
            "Component Harness promotion router-inventory delta witness remediation evidence request consumes the remediation plan and exposes six operator evidence request slots without submitting evidence, accepting evidence, authorizing witness minting, minting a witness, applying a delta, mutating router inventory, or granting authority.",
            [
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_schema_valid",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_submission_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_acceptance_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_missing_slot",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_mutation_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_schema_valid": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_schema_valid_and_write",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_match_runtime_projection": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_match_runtime_projection",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_submission_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_submission_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_acceptance_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_acceptance_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_missing_slot": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_missing_slot",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_mutation_drift": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_reject_mutation_drift",
                ],
            },
        ),
        _surface(
            "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
            ["component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.py",
                "schemas/component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.schema.json",
                (
                    "examples/"
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger."
                    "governed_connector_framework.json"
                ),
                "scripts/validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.py",
                "tests/test_validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.py",
            ],
            "Component Harness promotion router-inventory delta witness remediation evidence request status ledger consumes the evidence request and exposes six read-only unresolved request statuses without submitting evidence, accepting evidence, rejecting evidence, authorizing witness minting, minting a witness, applying a delta, mutating router inventory, or granting authority.",
            [
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_schema_valid",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_match_runtime_projection",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_submission_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_acceptance_and_rejection_overclaim",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_missing_status_record",
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_mutation_drift",
            ],
            runtime_witness_anchor_aliases={
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_schema_valid": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_schema_valid_and_write",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_match_runtime_projection": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_match_runtime_projection",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_submission_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_submission_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_acceptance_and_rejection_overclaim": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_acceptance_and_rejection_overclaim",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_missing_status_record": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_missing_status_record",
                ],
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_mutation_drift": [
                    "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_mutation_drift",
                ],
            },
        ),
        _surface(
            "component_graph",
            ["component_graph"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_graph.py",
                "schemas/component_graph.schema.json",
                "examples/component_graph.foundation.json",
                "scripts/validate_component_graph.py",
                "tests/test_validate_component_graph.py",
            ],
            "Component Harness graph joins registry dependencies, request-path previews, bundle memberships, and autopsy blockers into one read-only relationship projection without granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_graph_schema_valid",
                "component_graph_example_matches_runtime_projection",
                "component_graph_rejects_unregistered_edge",
                "component_graph_covers_blocked_paths",
                "component_graph_denies_live_authority",
            ],
            runtime_witness_anchor_aliases={
                "component_graph_schema_valid": [
                    "component_graph_schema_valid_and_write",
                ],
                "component_graph_example_matches_runtime_projection": [
                    "component_graph_example_matches_runtime_projection",
                ],
                "component_graph_rejects_unregistered_edge": [
                    "component_graph_rejects_unregistered_edge_and_authority_drift",
                ],
                "component_graph_covers_blocked_paths": [
                    "component_graph_covers_every_component_with_blocked_path",
                ],
                "component_graph_denies_live_authority": [
                    "component_graph_example_matches_runtime_projection",
                    "component_graph_rejects_unregistered_edge_and_authority_drift",
                ],
            },
        ),
        _surface(
            "component_dead_detector",
            ["component_dead_component_detection"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_dead_detector.py",
                "schemas/component_dead_component_detection.schema.json",
                "examples/component_dead_component_detection.foundation.json",
                "scripts/validate_component_dead_detector.py",
                "tests/test_validate_component_dead_detector.py",
            ],
            "Component Harness dead-component detector classifies active, watch, blocked-governed, and dead-candidate components from graph/read-model evidence without granting execution, connector, mutation, or terminal closure authority.",
            [
                "component_dead_detector_schema_valid",
                "component_dead_detector_example_matches_runtime_projection",
                "component_dead_detector_rejects_authority_drift",
                "component_dead_detector_separates_blocked_from_dead",
                "component_dead_detector_reports_zero_foundation_dead_candidates",
            ],
            runtime_witness_anchor_aliases={
                "component_dead_detector_schema_valid": [
                    "component_dead_detector_schema_valid_and_write",
                ],
                "component_dead_detector_example_matches_runtime_projection": [
                    "component_dead_detector_example_matches_runtime_projection",
                ],
                "component_dead_detector_rejects_authority_drift": [
                    "component_dead_detector_rejects_authority_and_summary_drift",
                ],
                "component_dead_detector_separates_blocked_from_dead": [
                    "component_dead_detector_keeps_blocked_governed_separate_from_dead_candidate",
                ],
                "component_dead_detector_reports_zero_foundation_dead_candidates": [
                    "component_dead_detector_schema_valid_and_write",
                    "component_dead_detector_keeps_blocked_governed_separate_from_dead_candidate",
                ],
            },
        ),
        _surface(
            "component_lifecycle_transition_receipts",
            ["component_lifecycle_transition_receipts"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "schemas/component_lifecycle_transition_receipts.schema.json",
                "examples/component_lifecycle_transition_receipts.foundation.json",
                "scripts/validate_component_lifecycle_transition_receipts.py",
                "tests/test_validate_component_lifecycle_transition_receipts.py",
            ],
            "Component Harness lifecycle transition receipts bind each current component lifecycle state to evidence, allowed transition graph, validator refs, and live-authority denial without granting execution, mutation, connector, external effect, or terminal closure authority.",
            [
                "component_lifecycle_transition_receipts_validate_and_write",
                "component_lifecycle_transition_receipts_reject_missing_component_receipt",
                "component_lifecycle_transition_receipts_reject_state_drift",
                "component_lifecycle_transition_receipts_reject_live_authority_drift",
                "component_lifecycle_transition_receipts_reject_missing_evidence",
            ],
            runtime_witness_anchor_aliases={
                "component_lifecycle_transition_receipts_validate_and_write": [
                    "component_lifecycle_transition_receipts_validate_and_write",
                ],
                "component_lifecycle_transition_receipts_reject_missing_component_receipt": [
                    "component_lifecycle_transition_receipts_reject_missing_component_receipt",
                ],
                "component_lifecycle_transition_receipts_reject_state_drift": [
                    "component_lifecycle_transition_receipts_reject_state_drift",
                ],
                "component_lifecycle_transition_receipts_reject_live_authority_drift": [
                    "component_lifecycle_transition_receipts_reject_live_authority_drift",
                ],
                "component_lifecycle_transition_receipts_reject_missing_evidence": [
                    "component_lifecycle_transition_receipts_reject_missing_evidence",
                ],
            },
        ),
        _surface(
            "component_authority_envelope_witnesses",
            ["component_authority_envelope_witnesses"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/component_authority_envelope_witnesses.py",
                "schemas/component_authority_envelope_witnesses.schema.json",
                "examples/component_authority_envelope_witnesses.foundation.json",
                "scripts/validate_component_authority_envelope_witnesses.py",
                "tests/test_validate_component_authority_envelope_witnesses.py",
            ],
            "Component Harness authority envelope witnesses bind each registered component to its current registry authority posture, deny live effects, and require separate upgrade witnesses before promotion.",
            [
                "component_authority_envelope_witnesses_validate_and_write",
                "component_authority_envelope_witnesses_reject_missing_component_witness",
                "component_authority_envelope_witnesses_reject_authority_drift",
                "component_authority_envelope_witnesses_reject_state_drift",
                "component_authority_envelope_witnesses_reject_missing_evidence",
            ],
            runtime_witness_anchor_aliases={
                "component_authority_envelope_witnesses_validate_and_write": [
                    "component_authority_envelope_witnesses_validate_and_write",
                ],
                "component_authority_envelope_witnesses_reject_missing_component_witness": [
                    "component_authority_envelope_witnesses_reject_missing_component_witness",
                ],
                "component_authority_envelope_witnesses_reject_authority_drift": [
                    "component_authority_envelope_witnesses_reject_authority_drift",
                ],
                "component_authority_envelope_witnesses_reject_state_drift": [
                    "component_authority_envelope_witnesses_reject_state_drift",
                ],
                "component_authority_envelope_witnesses_reject_missing_evidence": [
                    "component_authority_envelope_witnesses_reject_missing_evidence",
                ],
            },
        ),
        _surface(
            "capability_worker_execution",
            ["/capability/execute"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/capability_worker.py",
                "gateway/capability_isolation.py",
                "gateway/capability_dispatch.py",
                "tests/test_gateway/test_capability_worker.py",
            ],
            "Restricted capability worker execution accepts only signed, hash-bound, isolated capability requests and returns signed receipt-bearing execution responses, including sandbox receipts for computer command execution.",
            [
                "signed_capability_request_required",
                "response_signature_verified",
                "input_hash_mismatch_rejected",
                "intent_boundary_mismatch_rejected",
                "non_isolated_boundary_rejected",
                "capability_worker_runs_computer_command_through_sandbox_receipt",
                "local_smoke_stub_bound_to_local_environment",
            ],
            runtime_witness_anchor_aliases={
                "signed_capability_request_required": [
                    "capability_worker_rejects_bad_signature",
                    "capability_worker_executes_signed_payment_request",
                ],
                "response_signature_verified": [
                    "capability_worker_executes_signed_payment_request",
                ],
                "input_hash_mismatch_rejected": [
                    "capability_worker_rejects_tampered_input_hash",
                ],
                "intent_boundary_mismatch_rejected": [
                    "capability_worker_rejects_intent_boundary_mismatch",
                ],
                "non_isolated_boundary_rejected": [
                    "capability_worker_rejects_non_isolated_boundary",
                ],
                "local_smoke_stub_bound_to_local_environment": [
                    "default_capability_worker_smoke_stub_is_local_only",
                ],
            },
        ),
        _surface(
            "read_only_first_worker_path",
            [
                "repository.inspect_read_only",
                "build_read_only_repository_inspection_lease",
                "build_worker_failure_receipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/read_only_repository_worker.py",
                "gateway/worker_failure_receipt.py",
                "schemas/read_only_first_worker_path.schema.json",
                "schemas/worker_failure_receipt.schema.json",
                "examples/read_only_first_worker_path.foundation.json",
                "scripts/validate_read_only_first_worker_path.py",
                "tests/test_validate_read_only_first_worker_path.py",
                "tests/test_gateway/test_read_only_repository_worker.py",
                "tests/test_gateway/test_worker_failure_receipt.py",
            ],
            "Foundation Mode first worker path selects local read-only repository inspection, rejects mutation, network, secret, and out-of-bound path inputs, emits worker-mesh receipts with redacted evidence, and maps failed or partial worker dispatches to non-terminal recovery receipts.",
            [
                "read_only_first_worker_path_example_passes",
                "read_only_first_worker_path_rejects_mutation_authority",
                "read_only_first_worker_path_rejects_missing_path_boundary",
                "read_only_repository_worker_dispatches_schema_valid_receipt",
                "read_only_repository_worker_redacts_secret_like_matches",
                "read_only_repository_worker_rejects_path_boundary_violation",
                "read_only_repository_worker_rejects_mutation_and_network_inputs",
                "worker_failure_receipt_validates_partial_completion",
                "worker_failure_receipt_classifies_rejected_before_handler",
                "worker_failure_receipt_rejects_success_source",
                "worker_failure_receipt_rejects_impossible_unit_counts",
            ],
        ),
        _surface(
            "read_only_document_worker_path",
            [
                "document.inspect_read_only",
                "build_read_only_document_inspection_lease",
                "create_read_only_document_inspection_handler",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/read_only_document_worker.py",
                "schemas/read_only_document_worker_path.schema.json",
                "examples/read_only_document_worker_path.foundation.json",
                "scripts/validate_read_only_document_worker_path.py",
                "tests/test_validate_read_only_document_worker_path.py",
                "tests/test_gateway/test_read_only_document_worker.py",
            ],
            "Foundation Mode document worker path selects local text-like read-only document inspection, rejects mutation, network, secrets, rich binary parsing, unsupported formats, and out-of-root path inputs, and emits worker-mesh receipts with redacted evidence.",
            [
                "read_only_document_worker_path_example_passes",
                "read_only_document_worker_path_rejects_rich_document_parsing",
                "read_only_document_worker_path_rejects_missing_format_allowlist",
                "read_only_document_worker_dispatches_schema_valid_receipt",
                "read_only_document_worker_redacts_secret_like_matches",
                "read_only_document_worker_rejects_path_boundary_violation",
                "read_only_document_worker_rejects_unsupported_format",
                "read_only_document_worker_reports_text_decode_failure",
                "read_only_document_worker_rejects_mutation_and_network_inputs",
                "read_only_document_worker_rejects_secret_like_input_values",
            ],
        ),
        _surface(
            "read_only_search_worker_path",
            [
                "enterprise.knowledge_search",
                "build_read_only_search_worker_lease",
                "create_read_only_search_handler",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/read_only_search_worker.py",
                "gateway/search_governance.py",
                "schemas/read_only_search_worker_path.schema.json",
                "schemas/search_decision_receipt.schema.json",
                "examples/read_only_search_worker_path.foundation.json",
                "scripts/validate_read_only_search_worker_path.py",
                "tests/test_validate_read_only_search_worker_path.py",
                "tests/test_gateway/test_read_only_search_worker.py",
            ],
            "Foundation Mode search worker path selects local text-like knowledge search, requires matching SearchDecisionReceipt admission, rejects mutation, network, secrets, web retrieval, unsupported sources, and out-of-root path inputs, and emits worker-mesh receipts with evidence-only redacted excerpts.",
            [
                "read_only_search_worker_path_example_passes",
                "read_only_search_worker_path_rejects_web_retrieval",
                "read_only_search_worker_path_rejects_missing_decision_receipt_obligation",
                "read_only_search_worker_dispatches_schema_valid_receipt",
                "read_only_search_worker_redacts_secret_like_matches",
                "read_only_search_worker_rejects_missing_decision_receipt",
                "read_only_search_worker_rejects_decision_query_mismatch",
                "read_only_search_worker_rejects_path_boundary_violation",
                "read_only_search_worker_rejects_unsupported_format",
                "read_only_search_worker_rejects_mutation_and_network_inputs",
                "read_only_search_worker_rejects_secret_like_input_values",
            ],
        ),
        _surface(
            "channel_approval_strength_policy",
            [
                "evaluate_channel_approval_strength",
                "validate_channel_approval_strength_policy",
                "channel_approval_strength_policy.foundation",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/channel_approval_strength.py",
                "schemas/channel_approval_strength_policy.schema.json",
                "examples/channel_approval_strength_policy.foundation.json",
                "scripts/validate_channel_approval_strength_policy.py",
                "tests/test_gateway/test_channel_approval_strength.py",
                "tests/test_validate_channel_approval_strength_policy.py",
            ],
            "Foundation Mode channel approval-strength policy blocks casual approvals without request ids, unbound cross-channel approvals, expired approvals, identity or tenant mismatches, high-risk approvals without operator-bound sessions, and critical approvals without dual control.",
            [
                "casual_yes_without_request_id_is_blocked",
                "bound_same_channel_medium_approval_is_allowed",
                "cross_channel_approval_requires_binding_witness",
                "cross_channel_bound_medium_approval_is_allowed",
                "high_risk_external_message_without_operator_session_is_blocked",
                "high_risk_operator_bound_approval_is_allowed",
                "critical_risk_requires_second_approval",
                "critical_dual_control_approval_is_allowed",
                "unknown_channel_is_untrusted_and_blocks",
                "channel_approval_strength_policy_example_passes",
                "channel_approval_strength_policy_rejects_default_allow",
                "channel_approval_strength_policy_rejects_missing_cross_channel_binding",
                "channel_approval_strength_policy_rejects_high_risk_downgrade",
                "channel_approval_strength_policy_rejects_missing_casual_text_obligation",
            ],
        ),
        _surface(
            "cross_channel_conversation_binding_policy",
            [
                "evaluate_cross_channel_conversation_binding",
                "build_cross_channel_conversation_binding_receipt",
                "gateway.cross_channel_conversation_binding",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/cross_channel_conversation_binding.py",
                "gateway/channel_approval_strength.py",
                "tests/test_gateway/test_cross_channel_conversation_binding.py",
                "docs/maps/MULLUSI_GAP_REGISTER.md",
            ],
            "Cross-channel conversation binding policy blocks same-channel conversation ambiguity, missing cross-channel binding witnesses, expired bindings, unauthorized actors, tenant or identity mismatches, unknown channels, and emits hash-only receipts without raw message exposure or live channel promotion claims.",
            [
                "same_channel_same_conversation_is_allowed",
                "same_channel_different_conversation_without_binding_is_blocked",
                "cross_channel_reply_without_witness_is_blocked",
                "cross_channel_bound_request_reply_is_allowed",
                "cross_channel_casual_reply_without_request_or_context_is_blocked",
                "cross_channel_expired_binding_is_blocked",
                "unknown_channel_blocks_with_explicit_reason",
                "binding_receipt_hides_raw_message_and_is_stable",
            ],
            runtime_witness_anchor_aliases={
                "same_channel_same_conversation_is_allowed": [
                    "same_channel_same_conversation_is_allowed"
                ],
                "same_channel_different_conversation_without_binding_is_blocked": [
                    "same_channel_different_conversation_without_binding_is_blocked"
                ],
                "cross_channel_reply_without_witness_is_blocked": [
                    "cross_channel_reply_without_witness_is_blocked"
                ],
                "cross_channel_bound_request_reply_is_allowed": [
                    "cross_channel_bound_request_reply_is_allowed"
                ],
                "cross_channel_casual_reply_without_request_or_context_is_blocked": [
                    "cross_channel_casual_reply_without_request_or_context_is_blocked"
                ],
                "cross_channel_expired_binding_is_blocked": [
                    "cross_channel_expired_binding_is_blocked"
                ],
                "unknown_channel_blocks_with_explicit_reason": [
                    "unknown_channel_blocks_with_explicit_reason"
                ],
                "binding_receipt_hides_raw_message_and_is_stable": [
                    "binding_receipt_hides_raw_message_and_is_stable"
                ],
            },
        ),
        _surface(
            "policy_denial_response_composer",
            [
                "compose_policy_denial_response",
                "gateway.denial_response",
                "GatewayRouter policy denial responses",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/denial_response.py",
                "gateway/router.py",
                "tests/test_gateway/test_denial_response.py",
                "tests/test_gateway/test_router.py",
                "docs/maps/MULLUSI_GAP_REGISTER.md",
            ],
            "Policy denial response composer maps governed denial kinds to user-facing redacted messages, records template metadata, required controls, and evidence refs, preserves existing audit fields, and avoids exposing internal reasons or raw payloads.",
            [
                "tenant_denial_template_is_user_facing_and_redacted",
                "approval_strength_denial_preserves_controls_without_raw_detail",
                "unknown_denial_kind_degrades_to_policy_denied",
                "unknown_tenant_returns_error",
                "channel_approval_callback_denies_mismatched_identity",
                "channel_approval_callback_blocks_high_risk_without_operator_session",
                "channel_approval_callback_blocks_self_approved_payment",
            ],
            runtime_witness_anchor_aliases={
                "tenant_denial_template_is_user_facing_and_redacted": [
                    "tenant_denial_template_is_user_facing_and_redacted"
                ],
                "approval_strength_denial_preserves_controls_without_raw_detail": [
                    "approval_strength_denial_preserves_controls_without_raw_detail"
                ],
                "unknown_denial_kind_degrades_to_policy_denied": [
                    "unknown_denial_kind_degrades_to_policy_denied"
                ],
                "unknown_tenant_returns_error": ["unknown_tenant_returns_error"],
                "channel_approval_callback_denies_mismatched_identity": [
                    "channel_approval_callback_denies_mismatched_identity"
                ],
                "channel_approval_callback_blocks_high_risk_without_operator_session": [
                    "channel_approval_callback_blocks_high_risk_without_operator_session"
                ],
                "channel_approval_callback_blocks_self_approved_payment": [
                    "channel_approval_callback_blocks_self_approved_payment"
                ],
            },
        ),
        _surface(
            "restricted_adapter_worker_boundaries",
            [
                "/browser/execute",
                "/document/execute",
                "/email-calendar/execute",
                "/messaging/execute",
                "/phone/execute",
                "/voice/execute",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/browser_worker.py",
                "gateway/document_worker.py",
                "gateway/email_calendar_worker.py",
                "gateway/messaging_worker.py",
                "gateway/phone_worker.py",
                "gateway/voice_worker.py",
                "tests/test_gateway/test_browser_worker.py",
                "tests/test_gateway/test_document_worker.py",
                "tests/test_gateway/test_email_calendar_worker.py",
                "tests/test_gateway/test_messaging_worker.py",
                "tests/test_gateway/test_phone_worker.py",
                "tests/test_gateway/test_voice_worker.py",
            ],
            "Restricted browser, document, email/calendar, messaging, phone, and voice workers reject unsigned requests, execute only signed governed actions, emit receipt-bearing signed responses, and bound malformed request details without echoing submitted payloads.",
            [
                "browser_worker_rejects_bad_signature",
                "browser_worker_executes_signed_open_request",
                "browser_worker_parse_error_detail_is_bounded",
                "document_worker_rejects_bad_signature",
                "document_worker_executes_signed_extract_text_request",
                "document_worker_parse_error_detail_is_bounded",
                "email_calendar_worker_rejects_bad_signature",
                "email_calendar_worker_executes_signed_draft_request",
                "email_calendar_worker_parse_error_detail_is_bounded",
                "messaging_worker_rejects_bad_signature",
                "messaging_worker_executes_signed_draft_request",
                "messaging_worker_parse_error_detail_is_bounded",
                "phone_worker_rejects_bad_signature",
                "phone_worker_executes_signed_receive_request",
                "phone_worker_parse_error_detail_is_bounded",
                "voice_worker_rejects_bad_signature",
                "voice_worker_executes_signed_intent_classification_request",
                "voice_worker_parse_error_detail_is_bounded",
            ],
        ),
        _surface(
            "llm_streaming",
            ["/api/v1/stream", "/api/v1/chat/stream"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/llm/completion.py",
                "mcoi/mcoi_runtime/app/routers/llm/chat.py",
                "mcoi/mcoi_runtime/app/streaming.py",
                "mcoi/tests/test_streaming.py",
                "mcoi/tests/test_server_phase200.py",
                "mcoi/tests/test_server_phase213.py",
                "schemas/streaming_budget_enforcement.schema.json",
                "docs/41_streaming_budget_enforcement.md",
            ],
            "SSE responses include precharge, first-byte, chunk-debit, and final-reconcile proof identifiers.",
            [
                "stream_returns_sse",
                "stream_contains_content",
                "stream_contains_budget_witnesses",
                "stream_budget_reservation_and_settlement",
                "stream_budget_cutoff_stops_delivery",
                "streaming_chat_returns_sse",
                "streaming_chat_exception_sanitized",
            ],
        ),
        _surface(
            "code_intelligence_operator_read_model",
            [
                "/operator/code-intelligence/read-model",
                "build_repo_map",
                "build_code_context",
                "create_code_context_receipt",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/code_intelligence_read_model.py",
                "gateway/server.py",
                "mcoi/mcoi_runtime/contracts/code_intelligence.py",
                "mcoi/mcoi_runtime/contracts/code_context.py",
                "mcoi/mcoi_runtime/core/code_intelligence.py",
                "mcoi/mcoi_runtime/core/code_context_builder.py",
                "tests/test_code_intelligence.py",
                "tests/test_code_context_builder.py",
                "tests/test_gateway/test_code_intelligence_read_model.py",
            ],
            "Code-intelligence operator read models expose repository maps, selected symbols, risk counts, bounded context receipts, and cost estimates without source content or execution authority.",
            [
                "code_intelligence_repo_map_detects_routes_schemas_dependencies",
                "code_context_bundle_bounds_symbols_tests_and_edges",
                "code_context_missing_affected_file_fails_closed",
                "code_intelligence_operator_read_model_hides_source_content",
                "code_intelligence_operator_endpoint_fails_closed_for_missing_file",
            ],
        ),
        _surface(
            "llm_completion",
            ["/api/v1/complete", "/api/v1/complete/safe", "/api/v1/complete/auto"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm/completion.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
                "mcoi/tests/test_server_phase199.py",
                "mcoi/tests/test_server_phase213.py",
                "mcoi/tests/test_server_phase214.py",
            ],
            "Completion routes are governed through budget, model routing, and proof bridge checks.",
            [
                "completion_returns_action_proof",
                "completion_records_budget_ledger",
                "completion_failure_is_bounded",
                "safe_completion_tracks_cost",
                "safe_completion_exception_sanitized",
                "auto_completion_routes_model",
                "auto_completion_exception_sanitized",
            ],
            runtime_witness_anchor_aliases={
                "completion_returns_action_proof": ["basic_completion"],
                "completion_records_budget_ledger": ["ledger_after_completion"],
                "completion_failure_is_bounded": [
                    "completion_failure_result_is_structured",
                    "completion_exception_is_sanitized",
                ],
                "safe_completion_tracks_cost": ["safe_complete_tracks_cost"],
                "safe_completion_exception_sanitized": ["safe_complete_exception_is_sanitized"],
                "auto_completion_routes_model": ["auto_complete"],
                "auto_completion_exception_sanitized": ["auto_complete_exception_is_sanitized"],
            },
        ),
        _surface(
            "llm_chat_workflow",
            ["/api/v1/chat", "/api/v1/chat/workflow", "/api/v1/chat/workflow/history"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm/chat.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
                "mcoi/tests/test_server_phase209.py",
                "mcoi/tests/test_server_phase210.py",
                "mcoi/tests/test_server_phase213.py",
            ],
            "Chat and workflow routes preserve governed request and action proof boundaries.",
            [
                "chat_completion_governed",
                "streaming_chat_returns_sse",
                "streaming_chat_multi_turn_history_preserved",
                "streaming_chat_governed",
                "streaming_chat_contains_budget_witnesses",
                "streaming_chat_exception_sanitized",
                "chat_workflow_history_bounded",
            ],
            runtime_witness_anchor_aliases={
                "chat_completion_governed": ["single_turn"],
                "streaming_chat_returns_sse": ["streaming_chat_returns_sse"],
                "streaming_chat_multi_turn_history_preserved": ["streaming_chat_multi_turn"],
                "streaming_chat_governed": ["streaming_chat_governed"],
                "streaming_chat_contains_budget_witnesses": [
                    "streaming_chat_contains_budget_witnesses",
                ],
                "streaming_chat_exception_sanitized": ["streaming_chat_exception_sanitized"],
                "chat_workflow_history_bounded": ["chat_workflow_history"],
            },
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
                "mcoi/mcoi_runtime/app/routers/llm/admin.py",
                "mcoi/mcoi_runtime/app/routers/llm/costs.py",
                "mcoi/mcoi_runtime/governance/guards/budget.py",
                "mcoi/tests/test_server_phase199.py",
                "mcoi/tests/test_server_phase209.py",
                "mcoi/tests/test_server_phase213.py",
            ],
            "Budget and cost surfaces expose bounded read models over governed spend state.",
            [
                "budget_summary_bounded",
                "safe_completion_tracks_cost",
                "cost_read_model_totals_bounded",
                "cost_top_spenders_bounded",
                "cost_by_model_bounded",
                "tenant_cost_projection_bounded",
            ],
            runtime_witness_anchor_aliases={
                "budget_summary_bounded": ["budget_summary"],
                "safe_completion_tracks_cost": ["safe_complete_tracks_cost"],
                "cost_read_model_totals_bounded": ["cost_summary"],
                "cost_top_spenders_bounded": ["top_spenders"],
                "cost_by_model_bounded": ["costs_by_model"],
                "tenant_cost_projection_bounded": ["cost_projection"],
            },
        ),
        _surface(
            "assistant_kernel_planning",
            [
                "/api/v1/assistant/profiles",
                "/api/v1/assistant/finance-ops/plans",
                "/api/v1/assistant/team-ops/plans",
                "/api/v1/personal-assistant/skills",
                "/api/v1/personal-assistant/requests/preview",
                "/api/v1/personal-assistant/approval-queue",
                "/api/v1/personal-assistant/approval-queue/preview",
                "/api/v1/personal-assistant/pilot/read-model",
                "/api/v1/personal-assistant/drafts",
                "/api/v1/personal-assistant/drafts/email/preview",
                "/api/v1/personal-assistant/drafts/calendar/preview",
                "/api/v1/personal-assistant/drafts/task/preview",
                "/api/v1/personal-assistant/memory-observations",
                "/api/v1/personal-assistant/memory-observations/preview",
                "/api/v1/personal-assistant/memory-observations/review/preview",
                "/api/v1/personal-assistant/teamops/gmail/live-probe/readiness",
                "/api/v1/personal-assistant/teamops/shared-inbox/plan/preview",
                "/api/v1/personal-assistant/github-codex/review/preview",
                "/api/v1/personal-assistant/research/source-compare/preview",
                "/api/v1/personal-assistant/math/reasoning/preview",
                "/api/v1/personal-assistant/planning/schedule/preview",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/assistant.py",
                "mcoi/mcoi_runtime/assistant_kernel/planner.py",
                "mcoi/mcoi_runtime/assistant_kernel/identity.py",
                "mcoi/mcoi_runtime/personal_assistant/console.py",
                "mcoi/mcoi_runtime/personal_assistant/planner.py",
                "mcoi/mcoi_runtime/personal_assistant/approval.py",
                "mcoi/mcoi_runtime/personal_assistant/memory.py",
                "mcoi/mcoi_runtime/personal_assistant/teamops.py",
                "mcoi/mcoi_runtime/personal_assistant/github_codex.py",
                "mcoi/mcoi_runtime/personal_assistant/research.py",
                "mcoi/mcoi_runtime/personal_assistant/planning.py",
                "mcoi/tests/test_assistant_router.py",
                "tests/test_assistant_kernel.py",
                "tests/test_gateway/test_personal_assistant_public_routes.py",
                "tests/test_personal_assistant_approval_queue.py",
                "tests/test_validate_personal_assistant_approval_decision.py",
                "tests/test_personal_assistant_memory.py",
                "tests/test_personal_assistant_memory_runtime.py",
                "tests/test_validate_personal_assistant_memory_review.py",
                "tests/test_personal_assistant_teamops.py",
                "tests/test_personal_assistant_planner.py",
                "tests/test_validate_personal_assistant_read_only_projection.py",
                "tests/test_validate_personal_assistant_draft_projection.py",
                "tests/test_validate_personal_assistant_teamops_projection.py",
                "tests/test_validate_personal_assistant_github_codex_projection.py",
                "tests/test_validate_personal_assistant_research_projection.py",
                "tests/test_validate_personal_assistant_math_projection.py",
                "tests/test_validate_personal_assistant_planning_projection.py",
                "schemas/personal_assistant_approval_queue.schema.json",
                "schemas/personal_assistant_approval_decision.schema.json",
                "schemas/personal_assistant_read_only_projection.schema.json",
                "schemas/personal_assistant_draft_projection.schema.json",
                "schemas/personal_assistant_memory_observation.schema.json",
                "schemas/personal_assistant_memory_read_model.schema.json",
                "schemas/personal_assistant_memory_review.schema.json",
                "schemas/personal_assistant_teamops_projection.schema.json",
                "schemas/personal_assistant_github_codex_projection.schema.json",
                "schemas/personal_assistant_research_projection.schema.json",
                "schemas/personal_assistant_math_projection.schema.json",
                "schemas/personal_assistant_planning_projection.schema.json",
                "examples/personal_assistant_approval_queue_read_model.json",
                "examples/personal_assistant_approval_decision_evidence.json",
                "examples/personal_assistant_read_only_projection.json",
                "examples/personal_assistant_draft_projection.json",
                "examples/personal_assistant_memory_read_model.json",
                "examples/personal_assistant_memory_review_evidence.json",
                "examples/personal_assistant_teamops_projection.json",
                "examples/personal_assistant_github_codex_projection.json",
                "examples/personal_assistant_research_projection.json",
                "examples/personal_assistant_math_projection.json",
                "examples/personal_assistant_planning_projection.json",
                "scripts/validate_personal_assistant_approval_queue.py",
                "scripts/validate_personal_assistant_approval_decision.py",
                "scripts/validate_personal_assistant_read_only_projection.py",
                "scripts/validate_personal_assistant_draft_projection.py",
                "scripts/validate_personal_assistant_memory_observation.py",
                "scripts/validate_personal_assistant_memory_review.py",
                "scripts/validate_personal_assistant_teamops_projection.py",
                "scripts/validate_personal_assistant_github_codex_projection.py",
                "scripts/validate_personal_assistant_research_projection.py",
                "scripts/validate_personal_assistant_math_projection.py",
                "scripts/validate_personal_assistant_planning_projection.py",
            ],
            "Assistant kernel and personal-assistant routes expose governed profile and skill read models, compile FinanceOps/TeamOps plans, and preview personal-assistant intent, WHQR, approval queue, governed Team Assistant Pilot package, memory observation, memory review, TeamOps shared-inbox plan, GitHub/Codex review plan, research source-compare plan, math reasoning plan, schedule planning preview, read-only, draft-only, and receipt projections without executing external effects.",
            [
                "assistant_profiles_read_model_bounded",
                "finance_ops_plan_requires_active_consent",
                "finance_ops_plan_projects_operator_queue",
                "assistant_plan_never_grants_execution_authority",
                "assistant_plan_errors_sanitized",
                "personal_assistant_skill_read_model_deployed_read_only",
                "personal_assistant_preview_compiles_without_execution",
                "personal_assistant_preview_blocks_with_whqr_step",
                "personal_assistant_preview_errors_sanitized",
                "personal_assistant_approval_queue_read_model_public_safe",
                "personal_assistant_approval_queue_decision_deferred",
                "personal_assistant_approval_decision_public_safe",
                "personal_assistant_pilot_read_model_public_safe",
                "personal_assistant_read_only_projection_public_safe",
                "personal_assistant_draft_projection_public_safe",
                "personal_assistant_memory_observation_read_model_public_safe",
                "personal_assistant_memory_observation_preview_candidate_only",
                "personal_assistant_memory_observation_review_no_effect",
                "personal_assistant_teamops_shared_inbox_plan_no_effect",
                "personal_assistant_github_codex_review_no_effect",
                "personal_assistant_research_source_compare_no_effect",
                "personal_assistant_math_reasoning_no_effect",
                "personal_assistant_planning_schedule_no_effect",
            ],
            runtime_witness_anchor_aliases={
                "assistant_profiles_read_model_bounded": [
                    "assistant_profiles_read_model_exposes_finance_ops_profile",
                ],
                "finance_ops_plan_requires_active_consent": [
                    "finance_ops_plan_blocks_without_active_payment_consent",
                ],
                "finance_ops_plan_projects_operator_queue": [
                    "finance_ops_plan_with_consent_projects_dispatch_ready_controls",
                ],
                "assistant_plan_never_grants_execution_authority": [
                    "finance_ops_plan_with_consent_projects_dispatch_ready_controls",
                    "finance_ops_plan_blocks_without_active_payment_consent",
                ],
                "assistant_plan_errors_sanitized": [
                    "finance_ops_plan_error_detail_is_bounded",
                ],
                "personal_assistant_skill_read_model_deployed_read_only": [
                    "personal_assistant_skill_read_model_is_deployed_read_only",
                ],
                "personal_assistant_preview_compiles_without_execution": [
                    "personal_assistant_preview_compiles_inbox_request_without_execution",
                    "preview_planner_emits_schema_valid_inbox_plan_and_receipt",
                ],
                "personal_assistant_preview_blocks_with_whqr_step": [
                    "personal_assistant_preview_blocks_unknown_request_with_whqr_step",
                    "preview_planner_blocks_unknown_request_with_clarification_skill",
                ],
                "personal_assistant_preview_errors_sanitized": [
                    "personal_assistant_preview_fails_closed_on_invalid_request",
                ],
                "personal_assistant_approval_queue_read_model_public_safe": [
                    "approval_queue_read_model_matches_schema_and_denies_execution",
                    "personal_assistant_approval_queue_read_model_is_public_safe",
                    "gateway_personal_assistant_approval_queue_read_model_is_empty_and_safe",
                    "gateway_personal_assistant_approval_queue_preview_records_pending_packet",
                ],
                "personal_assistant_approval_queue_decision_deferred": [
                    "approved_decision_links_evidence_and_still_defers_execution",
                    "gateway_personal_assistant_approval_queue_approved_still_defers_execution",
                ],
                "personal_assistant_approval_decision_public_safe": [
                    "personal_assistant_approval_decision_fixture_validates",
                    "runtime_approval_decision_blocks_effect_boundaries",
                    "approval_queue_expired_decision_records_receipt_without_execution",
                    "approval_queue_read_model_counts_expired_decisions",
                    "approval_decision_validator_rejects_execution_authority",
                    "approval_decision_validator_rejects_receipt_drift",
                    "approval_decision_validator_rejects_missing_decision_state",
                    "approval_decision_validator_rejects_raw_payload_and_secret",
                    "gateway_personal_assistant_approval_queue_expired_blocks_execution",
                ],
                "personal_assistant_pilot_read_model_public_safe": [
                    "gateway_personal_assistant_pilot_read_model_packages_controlled_demo",
                ],
                "personal_assistant_read_only_projection_public_safe": [
                    "personal_assistant_read_only_projection_fixture_validates",
                    "runtime_read_only_projection_blocks_all_effect_boundaries",
                    "read_only_projection_validator_rejects_execution_authority",
                    "read_only_projection_validator_rejects_receipt_drift",
                    "read_only_projection_validator_rejects_raw_payload_and_secret",
                ],
                "personal_assistant_draft_projection_public_safe": [
                    "personal_assistant_draft_projection_fixture_validates",
                    "runtime_draft_projection_blocks_effect_boundaries",
                    "draft_projection_validator_rejects_execution_authority",
                    "draft_projection_validator_rejects_approval_boundary_drift",
                    "draft_projection_validator_rejects_receipt_drift",
                    "draft_projection_validator_rejects_raw_payload_and_secret",
                ],
                "personal_assistant_memory_observation_read_model_public_safe": [
                    "personal_assistant_memory_read_model_validator_accepts_example",
                    "memory_observation_ledger_indexes_candidates_without_live_memory_write",
                    "gateway_personal_assistant_memory_read_model_is_empty_and_safe",
                ],
                "personal_assistant_memory_observation_preview_candidate_only": [
                    "prepare_memory_observation_emits_schema_ready_candidate_and_receipt",
                    "personal_assistant_memory_read_model_validator_rejects_live_write_claim",
                    "gateway_personal_assistant_memory_preview_prepares_candidate_without_write",
                    "gateway_personal_assistant_memory_preview_rejects_raw_payload_and_activation",
                ],
                "personal_assistant_memory_observation_review_no_effect": [
                    "personal_assistant_memory_review_fixture_validates",
                    "runtime_memory_review_blocks_effect_boundaries",
                    "memory_review_runtime_requires_decision_specific_bindings",
                    "memory_review_validator_rejects_memory_write_authority",
                    "memory_review_validator_rejects_receipt_drift",
                    "memory_review_validator_rejects_missing_decision_state",
                    "memory_review_validator_rejects_raw_payload_and_secret",
                    "gateway_personal_assistant_memory_review_preview_records_no_effect_review",
                    "gateway_personal_assistant_memory_review_preview_rejects_missing_revision_binding",
                    "gateway_personal_assistant_memory_review_preview_rejects_raw_payload",
                ],
                "personal_assistant_teamops_shared_inbox_plan_no_effect": [
                    "personal_assistant_teamops_projection_fixture_validates",
                    "runtime_teamops_projection_blocks_effect_boundaries",
                    "teamops_projection_validator_rejects_live_execution_authority",
                    "teamops_projection_validator_rejects_receipt_drift",
                    "teamops_projection_validator_rejects_raw_payload_and_secret",
                    "teamops_shared_inbox_plan_emits_blocked_handoff_without_provider_call",
                    "teamops_shared_inbox_plan_accepts_ready_evidence_but_does_not_execute_probe",
                    "gateway_personal_assistant_teamops_preview_plans_without_provider_call",
                    "gateway_personal_assistant_teamops_preview_rejects_missing_connector_proof",
                    "gateway_personal_assistant_teamops_preview_rejects_raw_payload",
                ],
                "personal_assistant_github_codex_review_no_effect": [
                    "personal_assistant_github_codex_projection_fixture_validates",
                    "runtime_github_codex_projection_blocks_effect_boundaries",
                    "github_codex_projection_validator_rejects_live_execution_authority",
                    "github_codex_projection_validator_rejects_receipt_drift",
                    "github_codex_projection_validator_rejects_raw_diff_and_secret",
                    "github_codex_projection_requires_ready_and_blocked_items",
                    "gateway_personal_assistant_github_codex_preview_reviews_without_github_call",
                    "gateway_personal_assistant_github_codex_preview_rejects_missing_connector_proof",
                    "gateway_personal_assistant_github_codex_preview_rejects_secret_like_summary",
                ],
                "personal_assistant_research_source_compare_no_effect": [
                    "personal_assistant_research_projection_fixture_validates",
                    "runtime_research_projection_blocks_effect_boundaries",
                    "research_projection_validator_rejects_live_execution_authority",
                    "research_projection_validator_rejects_receipt_drift",
                    "research_projection_validator_rejects_raw_body_and_secret",
                    "research_projection_validator_requires_ready_and_blocked_items",
                    "gateway_personal_assistant_research_preview_compares_without_web_search",
                    "gateway_personal_assistant_research_preview_rejects_non_research_intent",
                    "gateway_personal_assistant_research_preview_rejects_raw_source_body",
                ],
                "personal_assistant_math_reasoning_no_effect": [
                    "personal_assistant_math_projection_fixture_validates",
                    "runtime_math_projection_blocks_effect_boundaries",
                    "math_projection_validator_rejects_money_or_write_authority",
                    "math_projection_validator_rejects_receipt_drift",
                    "math_projection_validator_rejects_raw_private_and_secret",
                    "math_projection_validator_requires_ready_and_blocked_items",
                    "math_projection_runtime_rejects_secret_like_value",
                    "gateway_personal_assistant_math_preview_compares_without_effects",
                    "gateway_personal_assistant_math_preview_rejects_non_math_intent",
                    "gateway_personal_assistant_math_preview_rejects_raw_private_value",
                ],
                "personal_assistant_planning_schedule_no_effect": [
                    "personal_assistant_planning_projection_fixture_validates",
                    "runtime_planning_projection_blocks_effect_boundaries_and_assigns_capacity",
                    "planning_projection_validator_rejects_calendar_or_task_authority",
                    "planning_projection_validator_rejects_receipt_drift",
                    "planning_projection_validator_rejects_raw_private_and_secret",
                    "planning_projection_validator_requires_ready_and_blocked_items",
                    "planning_projection_runtime_rejects_secret_like_value",
                    "gateway_personal_assistant_planning_preview_assigns_without_effects",
                    "gateway_personal_assistant_planning_preview_rejects_non_planning_intent",
                    "gateway_personal_assistant_planning_preview_rejects_raw_private_item",
                ],
            },
        ),
        _surface(
            "operational_platform_read_models",
            [
                "/api/v1/bootstrap",
                "/api/v1/circuit-breaker",
                "/api/v1/dependencies",
                "/api/v1/dependencies/{name}/impact",
                "/api/v1/flags",
                "/api/v1/flags/{flag_id}",
                "/api/v1/grafana/dashboard",
                "/api/v1/llm/history",
                "/api/v1/metrics",
                "/api/v1/rate-limit/status",
                "/api/v1/rate-limits/{client_id}",
                "/api/v1/sla",
                "/api/v1/sla/violations",
                "/gateway/status",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "mcoi/mcoi_runtime/app/routers/data/sla.py",
                "mcoi/mcoi_runtime/app/routers/llm/admin.py",
                "mcoi/mcoi_runtime/app/routers/ops/dependencies.py",
                "mcoi/mcoi_runtime/app/routers/ops/feature_flags.py",
                "mcoi/mcoi_runtime/app/routers/ops/metrics.py",
                "mcoi/mcoi_runtime/app/routers/ops/rate_limit.py",
                "mcoi/mcoi_runtime/core/feature_flags.py",
                "mcoi/mcoi_runtime/core/rate_limit_headers.py",
                "mcoi/mcoi_runtime/core/rate_limit_middleware.py",
                "mcoi/mcoi_runtime/governance/guards/rate_limit.py",
                "mcoi/tests/test_feature_flags.py",
                "mcoi/tests/test_rate_limit_headers.py",
                "mcoi/tests/test_rate_limiter.py",
                "mcoi/tests/test_grafana_dashboard.py",
                "mcoi/tests/test_server_phase199.py",
                "mcoi/tests/test_server_phase200.py",
                "mcoi/tests/test_server_phase202.py",
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_server_phase213.py",
                "mcoi/tests/test_server_phase220.py",
                "mcoi/tests/test_sla_monitor.py",
                "mcoi/tests/test_sla_router.py",
                "tests/test_gateway/test_webhooks.py",
            ],
            "Operational platform read-model routes aggregate bounded bootstrap, model history, dependency, feature-flag, metric, rate-limit, SLA, and gateway status state without mutation authority.",
            [
                "bootstrap_info",
                "bootstrap_has_stub",
                "circuit_breaker_status",
                "history_empty",
                "history_after_completion",
                "dependency_graph_startup_order_bounded",
                "dependency_impact_analysis_bounded",
                "list_flags",
                "summary",
                "check_flag_enabled",
                "check_flag_unknown",
                "tenant_override",
                "default_disabled",
                "get_metrics",
                "metrics_track_requests",
                "build_default",
                "default_json_roundtrip",
                "rate_limit_status",
                "status",
                "to_headers",
                "peek_does_not_consume",
                "consume_decrements",
                "exhaustion_triggers_retry_after",
                "sla_summary_endpoint_returns_bounded_governed_read_model",
                "sla_violations_endpoint_filters_by_sla_id",
                "violations_filtered",
                "health",
            ],
        ),
        _surface(
            "conversation_memory_lifecycle",
            [
                "/api/v1/conversation/message",
                "/api/v1/conversation/{conversation_id}",
                "/api/v1/conversations",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/conversations.py",
                "mcoi/mcoi_runtime/core/conversation_memory.py",
                "mcoi/tests/test_server_phase208.py",
                "mcoi/tests/test_conversation_memory.py",
            ],
            "Conversation memory routes append bounded tenant-scoped messages, expose conversation history read models, return bounded missing-conversation failures, and list conversations with tenant filtering.",
            [
                "conversation_message_appends_count",
                "conversation_history_read_model_bounded",
                "missing_conversation_bounded_404",
                "conversation_list_read_model_bounded",
                "conversation_store_tenant_filter",
            ],
            runtime_witness_anchor_aliases={
                "conversation_message_appends_count": ["add_message"],
                "conversation_history_read_model_bounded": ["get_conversation"],
                "missing_conversation_bounded_404": ["get_missing_conversation"],
                "conversation_list_read_model_bounded": ["list_conversations"],
                "conversation_store_tenant_filter": ["list_by_tenant"],
            },
        ),
        _surface(
            "coordination_checkpoint_lifecycle",
            [
                "/api/v1/coordination/checkpoint",
                "/api/v1/coordination/restore",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/ops/coordination.py",
                "mcoi/mcoi_runtime/core/coordination.py",
                "mcoi/mcoi_runtime/core/coordination_persistence.py",
                "mcoi/mcoi_runtime/persistence/coordination_store.py",
                "mcoi/tests/test_coordination_http_endpoints.py",
                "mcoi/tests/test_coordination_engine_persistence.py",
                "mcoi/tests/test_coordination_checkpoint_persistence.py",
            ],
            "Coordination checkpoint routes save lease-bound coordination snapshots, restore governed checkpoints, and return bounded missing-checkpoint errors.",
            [
                "coordination_checkpoint_audited",
                "coordination_restore_load_governed",
                "coordination_restore_resumes_checkpoint",
                "coordination_checkpoint_save_governed",
                "coordination_checkpoint_lease_bound",
                "coordination_store_path_traversal_rejected",
                "coordination_restore_policy_checked",
                "coordination_policy_drift_requires_review",
                "coordination_restore_missing_bounded",
                "coordination_restore_missing_is_bounded",
            ],
            runtime_witness_anchor_aliases={
                "coordination_checkpoint_audited": [
                    "checkpoint_appears_in_audit",
                    "restore_appears_in_audit",
                ],
                "coordination_restore_load_governed": [
                    "restore_checkpoint",
                    "save_restore_round_trip",
                ],
                "coordination_restore_resumes_checkpoint": [
                    "restore_checkpoint",
                    "idempotent_restore",
                    "empty_state_round_trip",
                ],
                "coordination_checkpoint_save_governed": [
                    "save_checkpoint",
                    "save_restore_round_trip",
                ],
                "coordination_checkpoint_lease_bound": ["expired_lease_rejected"],
                "coordination_store_path_traversal_rejected": [
                    "path_traversal_blocked"
                ],
                "coordination_restore_policy_checked": [
                    "policy_pack_drift_needs_review"
                ],
                "coordination_policy_drift_requires_review": [
                    "policy_pack_drift_needs_review"
                ],
                "coordination_restore_missing_bounded": [
                    "restore_missing_checkpoint_returns_404",
                    "restore_without_store_raises",
                ],
                "coordination_restore_missing_is_bounded": [
                    "restore_missing_checkpoint_returns_404",
                    "restore_without_store_raises",
                ],
            },
        ),
        _surface(
            "engineering_puzzle_governance",
            [
                "/api/v1/engineering-puzzle/candidates/judge",
                "/api/v1/engineering-puzzle/goal-delta",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/engineering_puzzle.py",
                "mcoi/mcoi_runtime/core/engineering_puzzle_kernel.py",
                "mcoi/tests/test_engineering_puzzle_control.py",
                "mcoi/tests/test_engineering_puzzle_router.py",
                "mcoi/tests/test_engineering_puzzle_server.py",
            ],
            "Engineering puzzle routes classify goal deltas and judge candidate arrangements through bounded governed search and sanitized validation failures.",
            [
                "engineering_goal_delta_classified",
                "engineering_candidate_judgment_governed",
                "engineering_puzzle_errors_sanitized",
            ],
        ),
        _surface(
            "data_export_lifecycle",
            [
                "/api/v1/export",
                "/api/v1/export/sources",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/export.py",
                "mcoi/mcoi_runtime/core/data_export.py",
                "mcoi/tests/test_data_export.py",
                "mcoi/tests/test_server_phase216.py",
            ],
            "Data export routes expose allowlisted source metadata, bounded export formats, field filters, and governed validation errors before returning export content.",
            [
                "data_export_sources_allowlisted",
                "data_export_format_validated",
                "data_export_limit_bounded",
                "data_export_errors_sanitized",
            ],
        ),
        _surface(
            "prompt_template_lifecycle",
            [
                "/api/v1/prompts",
                "/api/v1/prompts/render",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/prompts.py",
                "mcoi/mcoi_runtime/core/prompt_template_engine.py",
                "mcoi/tests/test_prompt_template_engine.py",
                "mcoi/tests/test_prompt_templates.py",
                "mcoi/tests/test_server_phase209.py",
                "mcoi/tests/test_prompt_template_lifecycle.py",
            ],
            "Prompt template routes list bounded template metadata, render declared variables, and sanitize optional execution failures behind the model circuit breaker.",
            [
                "prompt_template_list_bounded",
                "prompt_render_variables_validated",
                "prompt_execution_failure_sanitized",
                "prompt_execution_records_budgeted_result",
            ],
        ),
        _surface(
            "replay_trace_read_models",
            ["/api/v1/replay/traces"],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/execution_replay.py",
                "mcoi/tests/test_execution_replay.py",
                "mcoi/tests/test_server_phase207.py",
                "mcoi/tests/test_server_phase208.py",
            ],
            "Replay trace routes expose bounded execution trace summaries with trace hashes and frame counts without replay mutation authority.",
            [
                "replay_trace_list_bounded",
                "replay_trace_hash_projected",
                "replay_trace_summary_non_mutating",
            ],
        ),
        _surface(
            "schema_validation_registry",
            [
                "/api/v1/schemas",
                "/api/v1/schemas/validate",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/schemas.py",
                "mcoi/mcoi_runtime/core/schema_validator.py",
                "mcoi/tests/test_schema_validator.py",
                "mcoi/tests/test_server_phase208.py",
            ],
            "Schema validation routes list registered schemas and return explicit validation errors for schema-bound payload checks.",
            [
                "schema_registry_list_bounded",
                "schema_validation_errors_explicit",
                "schema_validation_result_typed",
            ],
        ),
        _surface(
            "semantic_search_read_models",
            [
                "/api/v1/search",
                "/api/v1/search/stats",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/search.py",
                "mcoi/mcoi_runtime/core/semantic_search.py",
                "mcoi/tests/test_semantic_search.py",
            ],
            "Semantic search routes execute bounded indexed search and expose index statistics without write authority.",
            [
                "semantic_search_limit_bounded",
                "semantic_search_scores_projected",
                "semantic_search_stats_bounded",
            ],
        ),
        _surface(
            "tenant_governance_lifecycle",
            [
                "/api/v1/tenant/budget",
                "/api/v1/tenant/{tenant_id}/budget",
                "/api/v1/tenant/{tenant_id}/ledger",
                "/api/v1/tenant/{tenant_id}/summary",
                "/api/v1/tenants",
                "/api/v1/usage/{tenant_id}",
                "/api/v1/analytics/{tenant_id}",
                "/api/v1/isolation/verify",
                "/api/v1/isolation/summary",
                "/api/v1/tenant-isolation",
                "/api/v1/tenant-isolation/audits",
                "/api/v1/quotas/summary",
                "/api/v1/quotas/{tenant_id}",
                "/api/v1/partitions",
                "/api/v1/tenant/register",
                "/api/v1/tenant/{tenant_id}/status",
                "/api/v1/tenant/{tenant_id}/gate",
                "/api/v1/tenant/gates",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/tenant.py",
                "mcoi/mcoi_runtime/governance/guards/budget.py",
                "mcoi/mcoi_runtime/governance/guards/tenant_gating.py",
                "mcoi/tests/test_server_phase202.py",
                "mcoi/tests/test_governance_endpoints.py",
                "mcoi/tests/test_tenant_budget.py",
                "mcoi/tests/test_tenant_gating.py",
                "mcoi/tests/test_tenant_ledger.py",
                "mcoi/tests/test_usage_reporter.py",
                "mcoi/tests/test_tenant_analytics.py",
                "mcoi/tests/test_tenant_quota.py",
                "mcoi/tests/test_phase232.py",
                "mcoi/tests/test_server_capability_helpers.py",
            ],
            "Tenant governance lifecycle routes bind budget mutation, tenant ledger and budget read models, registration, status transitions, and gate summaries to governed responses with audit records and bounded action proofs.",
            [
                "tenant_budget_create_emits_action_proof",
                "tenant_budget_create_records_audit",
                "tenant_budget_read_models_scoped_by_tenant",
                "tenant_ledger_queries_bounded",
                "tenant_registry_lifecycle_errors_sanitized",
                "tenant_register_emits_action_proof",
                "tenant_status_update_emits_action_proof",
                "tenant_gate_read_models_governed",
                "tenant_gate_persistence_read_model_included",
                "tenant_usage_read_model_scoped",
                "tenant_analytics_read_model_scoped",
                "tenant_isolation_verify_governed",
                "tenant_isolation_audits_bounded",
                "tenant_quota_read_models_bounded",
                "tenant_partition_read_model_bounded",
            ],
            {
                "tenant_budget_create_emits_action_proof": ["create_tenant_budget"],
                "tenant_budget_create_records_audit": ["audit_after_budget_create"],
                "tenant_budget_read_models_scoped_by_tenant": ["get_tenant_budget"],
                "tenant_ledger_queries_bounded": ["get_tenant_ledger"],
                "tenant_registry_lifecycle_errors_sanitized": ["register_invalid_status"],
                "tenant_register_emits_action_proof": ["register_new_tenant"],
                "tenant_status_update_emits_action_proof": ["suspend_tenant"],
                "tenant_gate_read_models_governed": ["get_existing_gate"],
                "tenant_gate_persistence_read_model_included": [
                    "list_gates_includes_store_backed_entries"
                ],
                "tenant_usage_read_model_scoped": ["generate"],
                "tenant_analytics_read_model_scoped": ["compute"],
                "tenant_isolation_verify_governed": [
                    "bootstrap_capability_services_wires_usage_templates_and_isolation"
                ],
                "tenant_isolation_audits_bounded": ["tenant_isolation"],
                "tenant_quota_read_models_bounded": ["get_usage"],
                "tenant_partition_read_model_bounded": ["max_partitions_error_is_bounded"],
            },
        ),
        _surface(
            "rbac_access_governance",
            [
                "/api/v1/rbac/bindings",
                "/api/v1/rbac/identities",
                "/api/v1/rbac/roles",
                "/api/v1/rbac/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/rbac.py",
                "mcoi/mcoi_runtime/core/access_runtime_integration.py",
                "mcoi/mcoi_runtime/contracts/access_runtime.py",
                "mcoi/tests/test_rbac_endpoints.py",
                "mcoi/tests/test_rbac_guard.py",
            ],
            "RBAC access-governance routes bind identity registration, role registration, role binding, and bounded summary read models to governed responses, audit records, and access-runtime contracts.",
            [
                "rbac_identity_registration_governed",
                "rbac_role_registration_governed",
                "rbac_role_binding_governed",
                "rbac_identity_creation_audited",
                "rbac_summary_bounded",
                "rbac_errors_sanitized",
            ],
            runtime_witness_anchor_aliases={
                "rbac_identity_registration_governed": ["create_identity"],
                "rbac_role_registration_governed": ["create_role"],
                "rbac_role_binding_governed": ["bind_role"],
                "rbac_identity_creation_audited": ["identity_creation_audited"],
                "rbac_summary_bounded": ["rbac_summary"],
                "rbac_errors_sanitized": [
                    "unknown_identity_denied",
                    "disabled_identity_denied",
                    "authenticated_evaluation_failure_fails_closed",
                ],
            },
        ),
        _surface(
            "runtime_config_management",
            [
                "/api/v1/config",
                "/api/v1/config/history",
                "/api/v1/config/update",
                "/api/v1/config/rollback",
                "/api/v1/config/watcher",
                "/api/v1/config/drift",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/ops/config.py",
                "mcoi/mcoi_runtime/core/config_reload.py",
                "mcoi/mcoi_runtime/core/config_watcher.py",
                "mcoi/mcoi_runtime/core/config_drift.py",
                "mcoi/tests/test_server_phase205.py",
                "mcoi/tests/test_server_phase207.py",
                "mcoi/tests/test_config_watcher.py",
                "mcoi/tests/test_config_drift.py",
                "mcoi/tests/test_e2e_integration.py",
            ],
            "Runtime configuration routes expose hash-bound read models, version history, audited hot-reload updates, bounded rollback, watcher status, and drift summaries through governed runtime configuration state.",
            [
                "config_read_model_hash_bound",
                "config_current_read_model_hash_bound",
                "config_history_versions_bounded",
                "config_history_bounded",
                "config_update_applies_atomically",
                "config_update_audited",
                "config_update_emits_event_and_audit",
                "config_update_emits_event",
                "config_rollback_requires_known_version",
                "config_rollback_version_checked",
                "config_watcher_errors_are_bounded",
                "config_watcher_status_bounded",
                "config_drift_secret_changes_are_critical",
                "config_drift_summary_bounded",
            ],
        ),
        _surface(
            "webhooks_proof_surface",
            [
                "/api/v1/webhooks/subscribe",
                "/api/v1/webhooks",
                "/api/v1/webhooks/deliveries",
                "/api/v1/webhooks/retry/summary",
                "/api/v1/webhooks/retry/dead-letters",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/agent_workflow.py",
                "mcoi/mcoi_runtime/governance/network/webhook.py",
                "mcoi/mcoi_runtime/core/webhook_retry.py",
                "mcoi/tests/test_server_phase205.py",
                "mcoi/tests/test_e2e_integration.py",
                "mcoi/tests/test_webhook_system.py",
                "mcoi/tests/test_webhook_retry.py",
                "mcoi/tests/test_webhook_dlq.py",
                "tests/test_gateway/test_webhook_dlq.py",
            ],
            "API webhook management routes bind subscription mutation, tenant-scoped subscription read models, delivery history, retry summary, dead-letter read models, and workflow delivery evidence to governed runtime state, audit records, and bounded retry failure evidence.",
            [
                "subscribe",
                "list_webhooks",
                "duplicate_subscribe_error_is_bounded",
                "emit_tenant_filter",
                "multiple_subscriptions",
                "webhook_deliveries",
                "delivery_history",
                "emit_queues_delivery",
                "emit_with_secret_signature",
                "disabled_subscription_skipped",
                "webhook_mutation_receipt_closes_effect_assurance",
                "summary_fields",
                "summary_reports_bounded_enqueue_reasons",
                "dead_letters_list",
                "bounded",
                "retry_exhaustion_reports_bounded_failure_reasons",
                "delivery_error_classifier_uses_stable_taxonomy",
            ],
        ),
        _surface(
            "operator_console_read_models",
            [
                "/api/v1/console",
                "/api/v1/console/home",
                "/api/v1/console/runs",
                "/api/v1/console/audit",
                "/api/v1/console/checkpoints",
                "/api/v1/console/providers",
                "/api/v1/console/scheduler",
                "/api/v1/console/shadow",
                "/api/v1/console/whqr/clarifications",
                "/api/v1/console/note-memory",
                "/api/v1/console/note-memory/view",
                "/api/v1/console/personal-assistant",
                "/api/v1/console/personal-assistant/readiness",
                "/api/v1/console/personal-assistant/view",
                "/api/v1/console/spatial-map",
                "/api/v1/console/spatial-map/view",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/console.py",
                "mcoi/mcoi_runtime/app/readiness.py",
                "mcoi/mcoi_runtime/app/routers/shadow.py",
                "mcoi/mcoi_runtime/app/console.py",
                "mcoi/mcoi_runtime/app/view_models.py",
                "mcoi/mcoi_runtime/personal_assistant/console.py",
                "mcoi/mcoi_runtime/core/spatial_governance.py",
                "mcoi/tests/test_operator_console.py",
                "mcoi/tests/test_console.py",
                "mcoi/tests/test_inceptadive_shadow_routes.py",
                "tests/test_personal_assistant_console.py",
                "tests/test_validate_personal_assistant_console_read_model.py",
            ],
            "Operator console routes expose bounded read-only runtime, audit, checkpoint, provider, scheduler, shadow posture, note-memory, personal-assistant lane-status, spatial governance panels, HTML views, and aggregate views with governed response witnesses.",
            [
                "console_home_returns_governed_runtime_vitals",
                "console_runs_bounds_recent_audit_entries",
                "console_audit_exposes_chain_intact_read_model",
                "console_checkpoints_expose_persisted_state_summary",
                "console_provider_and_scheduler_views_are_read_only",
                "shadow_console_route_returns_counts_without_raw_text",
                "console_note_memory_returns_read_only_lifecycle_summary",
                "console_note_memory_html_escapes_read_model",
                "console_note_memory_fails_closed_without_store_path",
                "console_personal_assistant_panel_read_model",
                "console_personal_assistant_html_view_renders_read_only_panel",
                "console_personal_assistant_lane_status_public_safe",
                "full_console_includes_spatial_map_read_model",
                "console_spatial_map_returns_panel_read_model",
                "console_spatial_map_html_renders_blockers",
                "console_whqr_clarifications_return_bounded_read_model",
                "console_personal_assistant_panel_read_model",
                "console_personal_assistant_html_view_renders_read_only_panel",
            ],
            runtime_witness_anchor_aliases={
                "console_home_returns_governed_runtime_vitals": ["console_home"],
                "console_runs_bounds_recent_audit_entries": ["console_runs"],
                "console_audit_exposes_chain_intact_read_model": ["console_audit"],
                "console_checkpoints_expose_persisted_state_summary": ["console_checkpoints"],
                "console_provider_and_scheduler_views_are_read_only": [
                    "console_providers",
                    "console_scheduler",
                ],
                "shadow_console_route_returns_counts_without_raw_text": [
                    "shadow_console_route_returns_counts_without_raw_text",
                ],
                "console_note_memory_returns_read_only_lifecycle_summary": [
                    "console_note_memory_enabled_read_model",
                ],
                "console_note_memory_html_escapes_read_model": [
                    "console_note_memory_html_disabled",
                    "console_note_memory_html_enabled_escapes_rows",
                ],
                "console_note_memory_fails_closed_without_store_path": [
                    "console_note_memory_mounted_without_store_path_fails_closed",
                ],
                "console_personal_assistant_panel_read_model": [
                    "console_personal_assistant_panel_read_model",
                ],
                "console_personal_assistant_html_view_renders_read_only_panel": [
                    "console_personal_assistant_html_view_renders_read_only_panel",
                ],
                "console_personal_assistant_lane_status_public_safe": [
                    "console_read_model_exposes_read_only_foundation_sections",
                    "personal_assistant_console_fixture_binds_rehearsal_receipt_viewer",
                    "personal_assistant_console_validator_rejects_lane_authority_drift",
                    "personal_assistant_console_read_model_fixture_validates",
                ],
                "full_console_includes_spatial_map_read_model": [
                    "full_console",
                ],
                "console_spatial_map_returns_panel_read_model": [
                    "console_spatial_map_panel_read_model",
                ],
                "console_spatial_map_html_renders_blockers": [
                    "console_spatial_map_html_view_renders_blockers",
                ],
                "console_whqr_clarifications_return_bounded_read_model": [
                    "console_whqr_clarifications_returns_active_job_status",
                    "console_whqr_clarifications_rejects_malformed_replay_metadata",
                ],
            },
        ),
        _surface(
            "agent_adapter_protocol",
            [
                "/api/v1/agent/register",
                "/api/v1/agent/heartbeat",
                "/api/v1/agent/action-request",
                "/api/v1/agent/action-result",
                "/api/v1/agent/checkpoint",
                "/api/v1/agent/restore",
                "/api/v1/agent/adapter/summary",
                "/api/v1/agents",
                "/api/v1/agents/{agent_id}/tasks",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/adapter.py",
                "mcoi/mcoi_runtime/app/routers/deps.py",
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/tests/test_agent_adapter_protocol.py",
                "mcoi/tests/test_server_phase205.py",
                "mcoi/tests/test_server_phase217.py",
            ],
            "Agent adapter protocol routes register external workers, maintain heartbeat state, pass action requests through the guard chain, record action results, checkpoint and restore coordination state, expose adapter summaries, and expose built-in agent task read models with bounded errors.",
            [
                "agent_register_emits_governed_identity",
                "agent_register_emits_audit_record",
                "agent_heartbeat_requires_registered_agent",
                "agent_action_request_runs_guard_chain",
                "agent_action_result_records_outcome",
                "agent_action_result_closes_tracked_action",
                "agent_goal_context_propagates_to_action_request",
                "agent_goal_context_propagates_to_response_and_audit",
                "agent_checkpoint_restore_errors_are_bounded",
                "agent_checkpoint_restore_roundtrip_governed",
                "agent_adapter_summary_is_governed_read_model",
                "agent_adapter_summary_bounded",
                "builtin_agent_registry_read_models_governed",
                "agent_error_contracts_bounded",
            ],
            {
                "agent_register_emits_governed_identity": ["register_agent"],
                "agent_register_emits_audit_record": ["register_agent"],
                "agent_heartbeat_requires_registered_agent": ["heartbeat_registered_agent"],
                "agent_action_request_runs_guard_chain": ["action_request_allowed"],
                "agent_action_result_records_outcome": ["action_result_submitted"],
                "agent_action_result_closes_tracked_action": ["full_governed_flow"],
                "agent_goal_context_propagates_to_action_request": [
                    "action_request_propagates_goal_hierarchy"
                ],
                "agent_goal_context_propagates_to_response_and_audit": [
                    "action_request_propagates_goal_hierarchy"
                ],
                "agent_checkpoint_restore_errors_are_bounded": [
                    "agent_restore_missing_checkpoint_is_bounded"
                ],
                "agent_checkpoint_restore_roundtrip_governed": [
                    "agent_checkpoint_restore_roundtrip"
                ],
                "agent_adapter_summary_is_governed_read_model": ["adapter_summary"],
                "agent_adapter_summary_bounded": ["adapter_summary"],
                "builtin_agent_registry_read_models_governed": [
                    "list_agents",
                    "agent_tasks",
                ],
                "agent_error_contracts_bounded": [
                    "heartbeat_unknown_agent_404",
                    "action_request_unknown_agent_404",
                    "action_result_unknown_action_404",
                    "agent_restore_missing_checkpoint_is_bounded",
                ],
            },
        ),
        _surface(
            "model_experiment_control",
            ["/api/v1/models", "/api/v1/ab-test", "/api/v1/ab-test/summary"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm/admin.py",
                "mcoi/mcoi_runtime/app/routers/llm/ab_test.py",
                "mcoi/tests/test_ab_testing.py",
                "mcoi/tests/test_server_phase214.py",
            ],
            "Model catalog and experiment control routes are declared as governed control surfaces.",
            [
                "model_catalog_list_bounded",
                "auto_completion_routes_model",
                "auto_completion_forced_model",
                "ab_test_single_model_result",
                "ab_test_two_models_cost_comparison",
                "ab_test_summary_bounded",
                "ab_test_failed_model_recorded",
            ],
            runtime_witness_anchor_aliases={
                "model_catalog_list_bounded": ["list_models"],
                "auto_completion_routes_model": ["auto_complete"],
                "auto_completion_forced_model": ["force_model"],
                "ab_test_single_model_result": ["single_model"],
                "ab_test_two_models_cost_comparison": ["two_models_cost"],
                "ab_test_summary_bounded": ["summary"],
                "ab_test_failed_model_recorded": ["failed_model"],
            },
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
            "proven",
            [
                "mcoi/mcoi_runtime/app/policy_version_integration.py",
                "mcoi/mcoi_runtime/app/routers/policy_versions.py",
                "mcoi/mcoi_runtime/governance/policy/versioning.py",
                "mcoi/tests/test_policy_version_endpoints.py",
                "mcoi/tests/test_policy_versioning.py",
            ],
            "Policy version routes expose immutable artifact registration, promotion, rollback, diff, shadow evaluation, and env-governed durable registry persistence.",
            [
                "policy_version_register_and_fetch",
                "policy_version_promote_diff_shadow_and_rollback",
                "policy_version_routes_fail_closed",
                "policy_artifact_hash_is_deterministic",
                "policy_registry_promotes_and_rolls_back_versions",
                "policy_diff_reports_changed_and_added_rules",
                "shadow_governance_compares_without_promoting",
                "registry_fails_closed_on_unknown_versions",
                "file_policy_registry_persists_versions_and_active_history",
                "file_policy_registry_rejects_tampered_artifact_hash",
                "file_policy_registry_rejects_unknown_active_pointer",
                "policy_version_registry_integration_selects_memory_or_file",
                "policy_version_registry_path_validation_requires_absolute_json_path",
            ],
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
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/pilot.py",
                "mcoi/mcoi_runtime/app/pilot_init.py",
                "mcoi/mcoi_runtime/app/pilot_provision_integration.py",
                "mcoi/tests/test_pilot_init.py",
                "docs/47_one_command_pilot_bringup.md",
            ],
            "Pilot provisioning returns deterministic scaffold artifacts, persists accepted provision records, exposes bounded operator history read models, and supports env-governed durable history persistence.",
            [
                "initialize_pilot_writes_complete_artifact_set",
                "initialize_pilot_is_deterministic_for_same_inputs",
                "build_pilot_scaffold_has_no_filesystem_side_effects",
                "pilot_provision_registry_persists_bounded_records",
                "file_pilot_provision_registry_persists_and_reloads_records",
                "file_pilot_provision_registry_rejects_tampered_record_count",
                "pilot_provision_registry_integration_selects_memory_or_file",
                "pilot_provision_registry_path_validation_requires_absolute_json_path",
                "initialize_pilot_fails_closed_on_existing_files",
                "pilot_provision_endpoint_returns_audited_scaffold",
                "pilot_provision_history_routes_return_accepted_records",
                "pilot_provision_detail_fails_closed_for_missing_record",
            ],
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
            [
                "sandbox_summary_is_deterministic",
                "sandbox_lineage_contains_bounded_causal_graph",
                "sandbox_policy_evaluations_are_read_only",
                "sandbox_summary_route",
                "sandbox_traces_route",
                "sandbox_lineage_route",
                "sandbox_missing_lineage_route_fails_closed",
                "sandbox_policy_evaluations_route",
            ],
        ),
        _surface(
            "federated_control_plane",
            [
                "/api/v1/federation/summary",
                "/api/v1/federation/clusters",
                "/api/v1/federation/policies",
                "/api/v1/federation/policy-sync",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/federated_control.py",
                "gateway/server.py",
                "mcoi/mcoi_runtime/app/routers/federation.py",
                "mcoi/mcoi_runtime/core/federated_control_plane.py",
                "mcoi/tests/test_federated_control_plane.py",
                "schemas/federated_control_snapshot.schema.json",
                "docs/51_federated_control_plane.md",
                "tests/test_gateway/test_federated_control.py",
            ],
            "Federated control-plane routes expose signed policy distribution, admin-gated regional metadata sync, and local enforcement receipts without tenant data replication.",
            [
                "signed_policy_metadata_only_sync",
                "federation_control_routes_publish_and_sync_policy_metadata",
                "invalid_signature_denied_before_local_acceptance",
                "policy_not_allowed_for_cluster_denied",
                "federation_policy_sync_route_returns_denied_receipt_for_disallowed_policy",
                "unsynced_policy_denied_locally",
                "tenant_region_mismatch_denied_locally",
                "central_data_transfer_forbidden",
                "federation_policy_publish_route_rejects_tenant_data_payload",
                "federated_snapshot_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "signed_policy_metadata_only_sync": [
                    "signed_policy_syncs_to_allowed_region_without_data_transfer",
                    "signed_policy_sync_preserves_residency_boundary",
                ],
                "invalid_signature_denied_before_local_acceptance": [
                    "invalid_signature_is_denied_before_local_acceptance",
                ],
                "policy_not_allowed_for_cluster_denied": [
                    "policy_not_allowed_for_cluster_is_denied",
                    "policy_sync_denies_policy_not_allowed_for_cluster",
                ],
                "federation_policy_sync_route_returns_denied_receipt_for_disallowed_policy": [
                    "federation_policy_sync_route_returns_denied_receipt_for_disallowed_policy",
                ],
                "unsynced_policy_denied_locally": ["local_enforcement_denies_unsynced_policy"],
                "tenant_region_mismatch_denied_locally": [
                    "tenant_region_mismatch_denies_locally",
                    "local_enforcement_denies_region_mismatch",
                ],
                "central_data_transfer_forbidden": [
                    "signed_policy_syncs_to_allowed_region_without_data_transfer",
                    "federation_summary_endpoint_returns_schema_valid_read_model",
                    "local_enforcement_allows_matching_residency_after_sync",
                    "federation_control_routes_publish_and_sync_policy_metadata",
                ],
                "federation_policy_publish_route_rejects_tenant_data_payload": [
                    "federation_policy_publish_route_rejects_tenant_data_payload",
                ],
                "federated_snapshot_schema_valid": [
                    "federated_control_snapshot_schema_exposes_locality_contract",
                    "federation_summary_endpoint_returns_schema_valid_read_model",
                ],
            },
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
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/finance_approval.py",
                "mcoi/mcoi_runtime/contracts/finance_approval_packet.py",
                "mcoi/mcoi_runtime/core/finance_approval/policy.py",
                "mcoi/mcoi_runtime/core/finance_approval/state_machine.py",
                "mcoi/mcoi_runtime/core/finance_approval/proof.py",
                "mcoi/tests/test_finance_approval_packet.py",
                "mcoi/tests/test_finance_approval_router.py",
                "schemas/finance_approval_email_calendar_binding_receipt.schema.json",
                "schemas/finance_approval_email_calendar_operator_input_request.schema.json",
                "schemas/finance_approval_email_calendar_live_receipt.schema.json",
                "schemas/finance_approval_handoff_packet.schema.json",
                "schemas/finance_approval_live_handoff_chain_validation.schema.json",
                "scripts/plan_finance_approval_live_handoff.py",
                "scripts/emit_finance_approval_email_calendar_binding_receipt.py",
                "scripts/emit_finance_approval_email_calendar_operator_input_request.py",
                "scripts/validate_finance_approval_email_calendar_binding_receipt.py",
                "scripts/validate_finance_approval_email_calendar_operator_input_request.py",
                "scripts/produce_finance_approval_handoff_packet.py",
                "scripts/validate_finance_approval_handoff_packet_schema.py",
                "scripts/validate_finance_approval_live_handoff_chain.py",
                "tests/test_plan_finance_approval_live_handoff.py",
                "tests/test_emit_finance_approval_email_calendar_binding_receipt.py",
                "tests/test_emit_finance_approval_email_calendar_operator_input_request.py",
                "tests/test_validate_finance_approval_email_calendar_binding_receipt.py",
                "tests/test_validate_finance_approval_email_calendar_operator_input_request.py",
                "tests/test_produce_finance_approval_handoff_packet.py",
                "tests/test_finance_approval_handoff_packet_schema.py",
                "tests/test_validate_finance_approval_live_handoff_chain.py",
                "schemas/finance_approval_payment_provider_binding_receipt.schema.json",
                "schemas/finance_approval_payment_closure_receipt.schema.json",
                "scripts/emit_finance_approval_payment_provider_binding_receipt.py",
                "scripts/produce_finance_approval_payment_closure_receipt.py",
                "scripts/validate_finance_approval_payment_provider_binding_receipt.py",
                "scripts/validate_finance_approval_payment_closure_receipt.py",
                "tests/test_emit_finance_approval_payment_provider_binding_receipt.py",
                "tests/test_produce_finance_approval_payment_closure_receipt.py",
                "tests/test_validate_finance_approval_payment_provider_binding_receipt.py",
                "tests/test_validate_finance_approval_payment_closure_receipt.py",
                "tests/test_finance_payment_provider_binding_examples.py",
                "examples/finance_approval_packet_blocked.json",
                "examples/finance_approval_packet_success.json",
                "examples/finance_payment_provider_binding_receipt_stripe.json",
                "examples/finance_payment_closure_receipt_stripe_bound.json",
            ],
            "Finance approval packet routes create policy-evaluated packet read models, expose a bounded operator read model, record explicit approval/effect receipts, and export bounded packet proofs for review-bound or closed cases.",
            [
                "finance_packet_policy_reasons_explicit",
                "blocked_packet_emits_no_effect",
                "approval_action_binds_approval_effect_and_closure_refs",
                "payment_handoff_prepared_without_live_payment_claim",
                "email_calendar_binding_receipt_requires_worker_token_and_readonly_scope",
                "email_calendar_operator_input_request_names_missing_inputs_without_values",
                "email_calendar_handoff_plan_requires_binding_receipt_ready",
                "email_calendar_handoff_packet_requires_live_receipt_ready",
                "payment_receipt_and_ledger_reconciliation_required_for_payment_closure",
                "payment_closure_receipt_validator_blocks_unbound_evidence",
                "payment_closure_receipt_producer_emits_ready_sandbox_evidence",
                "payment_provider_binding_receipt_redacts_credentials_and_scopes_provider",
                "payment_closure_producer_consumes_provider_binding_receipt",
                "payment_closure_validator_verifies_provider_binding_receipt_object",
                "payment_closure_receipt_producer_requires_provider_binding_for_nonsandbox",
                "payment_closure_example_evidence_validates_provider_binding_chain",
                "packet_proof_requires_policy_evidence_and_closure_for_closed_states",
                "operator_read_model_bounds_visible_packets_and_counts",
            ],
            {
                "finance_packet_policy_reasons_explicit": [
                    "create_list_get_and_proof_blocked_packet"
                ],
                "blocked_packet_emits_no_effect": [
                    "blocked_fixture_requires_review_and_emits_no_effect"
                ],
                "approval_action_binds_approval_effect_and_closure_refs": [
                    "approval_creates_effect_and_closed_proof"
                ],
                "payment_handoff_prepared_without_live_payment_claim": [
                    "approval_can_create_payment_handoff_without_live_payment_claim"
                ],
                "email_calendar_binding_receipt_requires_worker_token_and_readonly_scope": [
                    "finance_email_calendar_binding_receipt_blocks_without_worker_and_scope"
                ],
                "email_calendar_operator_input_request_names_missing_inputs_without_values": [
                    "operator_input_request_reports_missing_finance_bindings",
                    "validate_operator_input_request_accepts_blocked_request",
                ],
                "email_calendar_handoff_plan_requires_binding_receipt_ready": [
                    "current_finance_handoff_plan_scopes_to_email_calendar"
                ],
                "email_calendar_handoff_packet_requires_live_receipt_ready": [
                    "finance_handoff_packet_requires_ready_live_receipt",
                    "finance_handoff_packet_schema_rejects_live_receipt_status_drift",
                    "finance_live_handoff_chain_rejects_packet_live_receipt_path_mismatch",
                ],
                "payment_receipt_and_ledger_reconciliation_required_for_payment_closure": [
                    "payment_finalization_requires_provider_and_ledger_evidence_without_mutation"
                ],
                "payment_closure_receipt_validator_blocks_unbound_evidence": [
                    "validate_payment_closure_receipt_rejects_missing_ledger_evidence"
                ],
                "payment_closure_receipt_producer_emits_ready_sandbox_evidence": [
                    "produce_payment_closure_receipt_emits_ready_sandbox_receipt"
                ],
                "payment_provider_binding_receipt_redacts_credentials_and_scopes_provider": [
                    "payment_provider_binding_receipt_records_presence_without_values"
                ],
                "payment_closure_producer_consumes_provider_binding_receipt": [
                    "produce_payment_closure_receipt_derives_binding_ref_from_ready_receipt"
                ],
                "payment_closure_validator_verifies_provider_binding_receipt_object": [
                    "validate_payment_closure_receipt_accepts_ready_provider_binding_receipt"
                ],
                "payment_closure_receipt_producer_requires_provider_binding_for_nonsandbox": [
                    "produce_payment_closure_receipt_requires_non_sandbox_provider_binding"
                ],
                "payment_closure_example_evidence_validates_provider_binding_chain": [
                    "finance_payment_closure_example_binds_provider_receipt"
                ],
                "packet_proof_requires_policy_evidence_and_closure_for_closed_states": [
                    "proof_export_fails_for_closed_packet_without_closure_certificate"
                ],
                "operator_read_model_bounds_visible_packets_and_counts": [
                    "operator_read_model_summarizes_blocked_and_closed_packets"
                ],
            },
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
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/governance.py",
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
            "proven",
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
                "/api/v1/logs",
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
                "audit_logs_read_model_bounded",
            ],
            runtime_witness_anchor_aliases={
                "audit_chain_verify_endpoint": ["audit_verify"],
                "audit_summary_read_model": ["audit_summary"],
                "audit_anchor_checkpoint_created": ["create_anchor_endpoint"],
                "audit_anchor_verification_endpoint": ["verify_anchor_endpoint"],
                "audit_anchor_history_read_model": ["list_anchors_endpoint"],
                "audit_chain_hash_linked": [
                    "hash_chain",
                    "verify_valid_chain",
                    "post_prune_chain_still_verifies",
                ],
                "audit_logs_read_model_bounded": ["logs_read_model_bounded"],
            },
        ),
        _surface(
            "event_bus_operations",
            [
                "/api/v1/events",
                "/api/v1/events/publish",
                "/api/v1/events/store/summary",
                "/api/v1/events/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/audit.py",
                "mcoi/tests/test_server_phase206.py",
                "mcoi/tests/test_server_phase207.py",
            ],
            "Event bus operations publish hash-bound governed events, expose filtered event history, return bounded event-bus summaries, and surface event-store summary state for operational replay.",
            [
                "event_publish_hash_bound",
                "event_history_filter_bounded",
                "event_summary_bounded",
                "event_store_summary_governed",
                "pipeline_completion_event_visible",
                "config_update_event_visible",
            ],
            runtime_witness_anchor_aliases={
                "event_publish_hash_bound": ["publish_event"],
                "event_history_filter_bounded": ["filter_events_by_type"],
                "event_summary_bounded": ["events_summary"],
                "event_store_summary_governed": ["event_store_summary_governed"],
                "pipeline_completion_event_visible": ["pipeline_emits_event"],
                "config_update_event_visible": [
                    "config_update_emits_event",
                    "config_update_emits_event_and_audit",
                ],
            },
        ),
        _surface(
            "api_key_lifecycle",
            [
                "/api/v1/api-keys",
                "/api/v1/api-keys/{key_id}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/api_keys.py",
                "mcoi/mcoi_runtime/governance/auth/api_key.py",
                "mcoi/tests/test_api_key_lifecycle.py",
                "mcoi/tests/test_server_phase216.py",
            ],
            "API-key lifecycle routes create, list, revoke, rotate, expire, and inspect tenant-scoped credentials through governed validation errors, bounded lifecycle metadata, and audit-ready key state.",
            [
                "api_key_create_rejects_wildcard_when_disabled",
                "api_key_create_rejects_empty_scopes",
                "api_key_revoke_missing_is_bounded",
                "api_key_rotation_links_old_and_new_keys",
                "api_key_expiration_and_stale_detection",
            ],
            runtime_witness_anchor_aliases={
                "api_key_create_rejects_wildcard_when_disabled": [
                    "create_wildcard_api_key_returns_governed_validation_error",
                ],
                "api_key_create_rejects_empty_scopes": [
                    "create_api_key_empty_scopes_returns_governed_validation_error",
                ],
                "api_key_revoke_missing_is_bounded": [
                    "revoke_missing_api_key_returns_governed_not_found",
                ],
                "api_key_rotation_links_old_and_new_keys": ["rotate_links_old_to_new"],
                "api_key_expiration_and_stale_detection": [
                    "prune_expired",
                    "stale_keys_detected",
                ],
            },
        ),
        _surface(
            "conversation_memory_lifecycle",
            [
                "/api/v1/conversation/message",
                "/api/v1/conversation/{conversation_id}",
                "/api/v1/conversations",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/conversations.py",
                "mcoi/mcoi_runtime/core/conversation_memory.py",
                "mcoi/tests/test_server_phase208.py",
                "mcoi/tests/test_conversation_memory.py",
            ],
            "Conversation memory routes append governed conversation messages, expose bounded conversation history and summaries, preserve tenant-scoped store filtering, and return explicit missing-conversation failures.",
            [
                "conversation_message_append_increments_count",
                "conversation_history_returns_messages_and_summary",
                "conversation_missing_read_is_bounded",
                "conversation_multi_turn_history_preserved",
                "conversation_list_summary_bounded",
                "conversation_store_tenant_filtering",
                "conversation_memory_state_hash_changes",
                "conversation_memory_pruning_bounded",
            ],
            runtime_witness_anchor_aliases={
                "conversation_message_append_increments_count": ["add_message"],
                "conversation_history_returns_messages_and_summary": ["get_conversation", "summary"],
                "conversation_missing_read_is_bounded": ["get_missing"],
                "conversation_multi_turn_history_preserved": ["multi_turn"],
                "conversation_list_summary_bounded": ["list_conversations", "summary"],
                "conversation_store_tenant_filtering": ["list_by_tenant"],
                "conversation_memory_state_hash_changes": ["state_hash"],
                "conversation_memory_pruning_bounded": ["pruning"],
            },
        ),
        _surface(
            "ops_proof_surface",
            [
                "/api/v1/ops/benchmarks",
                "/api/v1/ops/imports",
                "/api/v1/ops/proof-bridge",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/ops/diagnostics.py",
                "mcoi/mcoi_runtime/core/governance_bench.py",
                "mcoi/mcoi_runtime/core/import_analyzer.py",
                "mcoi/mcoi_runtime/core/proof_bridge.py",
                "mcoi/tests/test_governance_endpoints.py",
                "mcoi/tests/test_governance_bench.py",
                "mcoi/tests/test_import_analyzer.py",
                "mcoi/tests/test_autonomous_fixes.py",
            ],
            "Operational diagnostics routes run governed benchmark summaries, expose bounded import-cycle analysis, and publish proof-bridge status read models without mutating runtime authority.",
            [
                "ops_benchmarks_return_governed_summary",
                "ops_benchmark_results_have_metrics",
                "ops_import_analysis_returns_dependency_summary",
                "ops_import_depth_distribution_bounded",
                "ops_proof_bridge_status_governed",
                "proof_bridge_registered_in_deps",
            ],
            runtime_witness_anchor_aliases={
                "ops_benchmarks_return_governed_summary": ["run_benchmarks"],
                "ops_benchmark_results_have_metrics": ["benchmark_results_have_metrics"],
                "ops_import_analysis_returns_dependency_summary": ["analyze_imports"],
                "ops_import_depth_distribution_bounded": ["imports_depth_distribution"],
                "ops_proof_bridge_status_governed": ["proof_bridge_status"],
            },
        ),
        _surface(
            "task_queue_lifecycle",
            [
                "/api/v1/queue/process",
                "/api/v1/queue/result/{task_id}",
                "/api/v1/queue/status",
                "/api/v1/queue/submit",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/task_queue.py",
                "mcoi/tests/test_task_queue.py",
                "mcoi/tests/test_server_phase215.py",
            ],
            "Task queue lifecycle routes submit bounded priority tasks, process one queued task at a time, expose queue status, and return stored task results with bounded missing-result failures.",
            [
                "task_queue_priority_order",
                "task_queue_depth_bounded",
                "task_queue_submit_endpoint",
                "task_queue_submit_mutation_receipt_emitted",
                "task_queue_process_endpoint",
                "task_queue_process_mutation_receipts_emitted",
                "task_queue_mutation_receipt_closes_effect_assurance",
                "task_queue_empty_process_bounded",
                "task_queue_result_retrieval",
                "task_queue_missing_result_bounded",
                "task_queue_errors_sanitized",
            ],
            runtime_witness_anchor_aliases={
                "task_queue_priority_order": ["priority_order"],
                "task_queue_depth_bounded": ["max_depth", "queue_status"],
                "task_queue_submit_endpoint": ["submit"],
                "task_queue_submit_mutation_receipt_emitted": [
                    "submit",
                    "submit_records_bounded_mutation_receipt",
                ],
                "task_queue_process_endpoint": ["process"],
                "task_queue_process_mutation_receipts_emitted": [
                    "process",
                    "process_records_dequeue_and_result_receipts",
                ],
                "task_queue_empty_process_bounded": ["process_empty", "pop_empty"],
                "task_queue_result_retrieval": ["get_result"],
                "task_queue_missing_result_bounded": ["get_missing_result"],
                "task_queue_errors_sanitized": [
                    "process_failure",
                    "process_timeout_failure_is_sanitized",
                    "record_result_sanitizes_manual_error",
                ],
            },
        ),
        _surface(
            "trace_observability_read_models",
            [
                "/api/v1/traces",
                "/api/v1/traces/slow",
                "/api/v1/traces/summary",
                "/api/v1/traces/{trace_id}",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/app/routers/ops/summaries.py",
                "mcoi/mcoi_runtime/core/request_tracing.py",
                "mcoi/tests/test_request_tracing.py",
            ],
            "Trace observability routes expose bounded request-tracing summaries, individual trace spans, slow-trace projections, and OpenTelemetry exporter summaries without mutation authority.",
            [
                "request_trace_summary_bounded",
                "request_trace_lookup_bounded",
                "missing_trace_returns_governed_404",
                "slow_trace_projection_bounded",
                "otel_trace_summary_bounded",
                "trace_context_roundtrip_tested",
            ],
            runtime_witness_anchor_aliases={
                "request_trace_summary_bounded": [
                    "trace_summary_route_bounded",
                    "summary",
                ],
                "request_trace_lookup_bounded": [
                    "trace_lookup_route_bounded",
                    "multiple_spans_same_trace",
                ],
                "missing_trace_returns_governed_404": [
                    "trace_lookup_missing_route_governed_404",
                    "get_nonexistent_trace",
                ],
                "slow_trace_projection_bounded": [
                    "slow_trace_route_bounded",
                    "slow_traces_empty",
                ],
                "otel_trace_summary_bounded": [
                    "otel_trace_summary_route_bounded",
                ],
                "trace_context_roundtrip_tested": [
                    "roundtrip_headers",
                ],
            },
        ),
        _surface(
            "agent_memory_lifecycle",
            [
                "/api/v1/memory/search",
                "/api/v1/memory/store",
                "/api/v1/memory/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/agent_memory.py",
                "mcoi/tests/test_agent_memory.py",
            ],
            "Agent memory lifecycle routes store tenant-scoped memories, search them through bounded relevance scoring, and expose bounded memory summaries without cross-tenant disclosure.",
            [
                "agent_memory_store_bounded",
                "agent_memory_search_relevance_scored",
                "agent_memory_tenant_isolation",
                "agent_memory_capacity_eviction",
                "agent_memory_summary_bounded",
                "agent_memory_forget_removes_entry",
            ],
            runtime_witness_anchor_aliases={
                "agent_memory_store_bounded": [
                    "store",
                    "memory_store_endpoint_bounded",
                ],
                "agent_memory_search_relevance_scored": [
                    "search",
                    "memory_search_endpoint_relevance_scored",
                ],
                "agent_memory_tenant_isolation": [
                    "tenant_isolation",
                ],
                "agent_memory_capacity_eviction": [
                    "capacity_eviction",
                ],
                "agent_memory_summary_bounded": [
                    "summary",
                    "memory_summary_endpoint_bounded",
                ],
                "agent_memory_forget_removes_entry": [
                    "forget",
                ],
            },
        ),
        _surface(
            "governance_explanation_lifecycle",
            [
                "/api/v1/explain/action",
                "/api/v1/explain/audit/{entry_index}",
                "/api/v1/explain/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/explain.py",
                "mcoi/mcoi_runtime/core/explanation_engine.py",
                "mcoi/tests/test_explanation_engine.py",
            ],
            "Governance explanation routes generate bounded explanations for prospective actions, audit entries, and explanation-engine summary state with governed responses and missing-entry errors.",
            [
                "explain_action_guard_chain_path_reported",
                "explain_action_returns_explanation_id",
                "explain_audit_entry_allowed_and_denied",
                "explain_audit_entry_goal_context_preserved",
                "explanation_cache_bounded",
                "explain_action_endpoint_governed",
                "explain_summary_endpoint_governed",
            ],
            runtime_witness_anchor_aliases={
                "explain_action_guard_chain_path_reported": [
                    "explain_action_endpoint",
                    "explain_action_no_guard_chain",
                ],
                "explain_audit_entry_allowed_and_denied": [
                    "explain_audit_entry_success",
                    "explain_audit_entry_denied",
                    "explain_audit_endpoint_governed_and_missing_entry",
                ],
                "explain_audit_entry_goal_context_preserved": [
                    "explain_audit_entry_with_goal_hierarchy",
                ],
                "explanation_cache_bounded": [
                    "cache_bounded",
                ],
                "explain_action_endpoint_governed": [
                    "explain_action_endpoint",
                ],
                "explain_summary_endpoint_governed": [
                    "explain_summary_endpoint",
                ],
            },
        ),
        _surface(
            "tool_registry_read_models",
            [
                "/api/v1/tools",
                "/api/v1/tools/history",
                "/api/v1/tools/llm-format",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/tools.py",
                "mcoi/mcoi_runtime/core/tool_use.py",
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_tool_use.py",
                "mcoi/tests/test_tool_registry_read_models.py",
            ],
            "Tool registry read-model routes expose registered tool metadata, bounded invocation history, and model-compatible schemas while invocation remains governed by the tool_invocation action-proof surface.",
            [
                "tool_registry_list_returns_registered_tools",
                "tool_registry_category_filter_bounded",
                "tool_llm_format_exports_input_schema",
                "tool_history_returns_bounded_summary",
                "tool_invocation_history_limit_applied",
                "tool_invoke_separate_action_proof_surface",
            ],
        ),
        _surface(
            "tool_permission_registry",
            [
                "/api/v1/tool-permissions",
                "/api/v1/tool-permissions/evaluate",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/tool_permissions.py",
                "mcoi/mcoi_runtime/app/tool_permission_integration.py",
                "mcoi/mcoi_runtime/core/tool_permission_primitives.py",
                "mcoi/mcoi_runtime/core/governed_tool_use.py",
                "mcoi/tests/test_tool_permission_primitives.py",
                "mcoi/tests/test_tool_permission_routes.py",
            ],
            "Tool permission registry routes expose tenant-scoped permission registration, bounded listing, dry-run evaluation without invoking tools, and env-governed durable registry persistence; governed execution consumes the same primitive registry.",
            [
                "permission_match_emits_stable_grammar_and_hashes",
                "permission_denies_missing_audit_without_executing",
                "permission_denies_schema_violations_fail_closed",
                "governed_tool_registry_applies_bound_permission_registry",
                "file_tool_permission_registry_persists_and_reloads_permissions",
                "file_tool_permission_registry_rejects_tampered_permission_identity",
                "tool_permission_registry_integration_selects_memory_or_file",
                "tool_permission_registry_path_validation_requires_absolute_json_path",
                "tool_permission_routes_register_list_and_evaluate",
                "tool_permission_routes_reject_duplicate_registration",
                "tool_permission_routes_deny_missing_permission_fail_closed",
            ],
        ),
        _surface(
            "structured_output_validation",
            [
                "/api/v1/output/parse",
                "/api/v1/output/schemas",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/output.py",
                "mcoi/mcoi_runtime/core/structured_output.py",
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_structured_output.py",
            ],
            "Structured-output routes parse model text against registered schemas, return explicit validation errors, preserve raw text in the parser contract, and expose bounded schema read models.",
            [
                "structured_output_parse_valid_json",
                "structured_output_parse_invalid_json",
                "structured_output_parse_unknown_schema_bounded",
                "structured_output_parse_markdown_json",
                "structured_output_schema_registration_validated",
                "structured_output_endpoint_parse_valid_and_invalid",
                "structured_output_schema_list_bounded",
            ],
            runtime_witness_anchor_aliases={
                "structured_output_parse_valid_json": [
                    "parse_valid_json",
                    "parse_valid",
                ],
                "structured_output_parse_invalid_json": [
                    "parse_no_json",
                    "parse_invalid",
                ],
                "structured_output_parse_unknown_schema_bounded": [
                    "unknown_schema",
                ],
                "structured_output_parse_markdown_json": [
                    "parse_markdown_json",
                ],
                "structured_output_schema_registration_validated": [
                    "register_rejects_unsupported_field_type",
                    "register_rejects_required_field_missing_from_schema",
                    "duplicate_register_is_bounded",
                ],
                "structured_output_endpoint_parse_valid_and_invalid": [
                    "parse_valid",
                    "parse_invalid",
                ],
                "structured_output_schema_list_bounded": [
                    "list_output_schemas",
                    "list_schemas",
                    "summary",
                ],
            },
        ),
        _surface(
            "operational_health_read_models",
            [
                "/api/v1/health/deep",
                "/api/v1/health/score",
                "/api/v1/health/extensions",
                "/api/v1/health/shadow",
                "/api/v1/health/v2",
                "/api/v1/health/v3",
                "/api/v1/health/witness",
                "/api/v1/health/dependencies",
                "/api/v1/health/remote",
                "/api/v1/dashboard",
                "/api/v1/plugins",
                "/api/v1/guards",
                "/api/v1/capabilities",
                "/api/v1/readiness",
                "/api/v1/spatial-map",
                "/api/v1/monitor",
                "/api/v1/shutdown/info",
                "/api/v1/correlation/active",
                "/api/v1/notifications/summary",
                "/api/v1/validation/schemas",
                "/api/v1/idempotency/summary",
                "/api/v1/compression/summary",
                "/api/v1/canary",
                "/api/v1/secrets/summary",
                "/api/v1/dedup/summary",
                "/api/v1/deploy/readiness",
                "/api/v1/migrations/summary",
                "/api/v1/retries/summary",
                "/api/v1/regions",
                "/api/v1/context/summary",
                "/api/v1/circuits/dashboard",
                "/api/v1/cache/stats",
                "/api/v1/backpressure",
                "/api/v1/version",
                "/api/v1/release",
                "/api/v1/release/latest",
                "/api/v1/snapshot",
                "/api/v1/snapshots",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/health.py",
                "mcoi/mcoi_runtime/app/routers/health_remote.py",
                "mcoi/mcoi_runtime/app/health_external.py",
                "mcoi/mcoi_runtime/app/readiness.py",
                "mcoi/mcoi_runtime/app/routers/shadow.py",
                "mcoi/mcoi_runtime/core/deep_health.py",
                "mcoi/mcoi_runtime/core/health_aggregator.py",
                "mcoi/mcoi_runtime/core/health_check_agg.py",
                "mcoi/mcoi_runtime/core/health_v3.py",
                "mcoi/mcoi_runtime/core/spatial_governance.py",
                "mcoi/mcoi_runtime/app/routers/ops/summaries.py",
                "mcoi/mcoi_runtime/app/routers/ops/release.py",
                "mcoi/mcoi_runtime/app/routers/ops/snapshots.py",
                "mcoi/tests/test_deep_health.py",
                "mcoi/tests/test_health_aggregator.py",
                "mcoi/tests/test_health_check_agg.py",
                "mcoi/tests/test_health_remote.py",
                "mcoi/tests/test_health_witness.py",
                "mcoi/tests/test_ready_dependency_aware.py",
                "mcoi/tests/test_inceptadive_shadow_routes.py",
                "mcoi/tests/test_operational_health_read_models.py",
                "mcoi/tests/test_phase232.py",
                "mcoi/tests/test_server_phase205.py",
                "mcoi/tests/test_server_phase210.py",
            ],
            "Operational health routes expose bounded read models for deep component diagnostics, weighted health score, optional extension and registry persistence posture, shadow posture, dependency readiness, remote endpoint health, degraded-state checks, v3 recovery tracking, and gated health witness proof receipts without open mutation authority.",
            [
                "deep_health_components_bounded",
                "health_score_range_bounded",
                "health_score_components_weighted",
                "extension_health_read_model_bounded",
                "shadow_health_route_returns_redacted_read_model",
                "shadow_routes_fallback_when_runtime_unregistered",
                "shadow_routes_respect_disabled_runtime_posture",
                "health_v2_degraded_state_supported",
                "health_v2_exception_sanitized",
                "health_v3_weighted_aggregation",
                "health_v3_recovery_tracking",
                "witness_disabled_by_default",
                "witness_verified_when_enabled",
                "witness_produces_distinct_verified_receipts",
                "health_routes_return_read_models",
                "ops_dashboard_read_model_bounded",
                "production_readiness_checks_bounded",
                "spatial_map_read_model_bounded",
                "spatial_path_missing_boundary_blocks_explicitly",
                "monitoring_vitals_read_model_bounded",
                "shutdown_info_read_model_bounded",
                "correlation_summary_read_model_bounded",
                "idempotency_summary_read_model_bounded",
                "deployment_readiness_read_model_bounded",
                "release_info_read_model_bounded",
                "system_snapshot_read_model_bounded",
            ],
        ),
        _surface(
            "agent_orchestration_lifecycle",
            [
                "/api/v1/orchestration",
                "/api/v1/orchestration/handoff",
                "/api/v1/orchestration/plans",
                "/api/v1/orchestration/plans/{plan_id}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/agent_orchestration.py",
                "mcoi/tests/test_agent_orchestration.py",
                "mcoi/tests/test_server_phase216.py",
            ],
            "Agent orchestration routes expose governed orchestration summaries, create bounded multi-agent plans, return bounded plan read models, and execute capability-checked handoffs.",
            [
                "orchestration_summary_bounded",
                "orchestration_plan_created_for_registered_agent",
                "orchestration_unknown_initiator_bounded",
                "orchestration_missing_plan_bounded",
                "orchestration_handoff_capability_checked",
                "orchestration_handoff_errors_sanitized",
                "orchestration_quorum_required",
                "orchestration_executor_errors_sanitized",
            ],
            runtime_witness_anchor_aliases={
                "orchestration_summary_bounded": [
                    "summary",
                    "orchestration_summary_endpoint_bounded",
                ],
                "orchestration_plan_created_for_registered_agent": [
                    "create_plan",
                    "orchestration_plan_endpoint_creates_registered_agent_plan",
                ],
                "orchestration_unknown_initiator_bounded": [
                    "create_plan_unknown_agent",
                    "orchestration_unknown_initiator_returns_governed_error",
                ],
                "orchestration_missing_plan_bounded": [
                    "missing_orchestration_plan_returns_governed_not_found",
                    "get_plan_records_lookup_proofs",
                ],
                "orchestration_handoff_capability_checked": [
                    "successful_handoff",
                    "handoff_missing_capability",
                    "orchestration_handoff_returns_proof_id",
                ],
                "orchestration_handoff_errors_sanitized": [
                    "handoff_missing_capability",
                    "handoff_unknown_source",
                    "handoff_unknown_target",
                    "handoff_blocks_unmanifested_required_capability",
                ],
                "orchestration_quorum_required": [
                    "quorum_reached",
                    "quorum_not_reached",
                    "execute_with_quorum",
                    "execute_without_quorum_fails",
                ],
                "orchestration_executor_errors_sanitized": [
                    "execute_with_failing_executor",
                    "execute_suppresses_executor_reserved_result_keys",
                ],
            },
        ),
        _surface(
            "workflow_execution_lifecycle",
            [
                "/api/v1/execute",
                "/api/v1/session",
                "/api/v1/ledger",
                "/api/v1/workflow/execute",
                "/api/v1/workflow/history",
                "/api/v1/workflow/traced",
                "/api/v1/cognitive/shadow/observations",
                "/api/v1/pipeline/execute",
                "/api/v1/pipeline/history",
                "/api/v1/templates",
                "/api/v1/templates/execute",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/workflow_orchestration.py",
                "mcoi/mcoi_runtime/app/routers/workflow.py",
                "mcoi/mcoi_runtime/core/agent_workflow.py",
                "mcoi/mcoi_runtime/core/traced_workflow.py",
                "tests/test_gateway/test_workflow_orchestration.py",
                "mcoi/tests/test_agent_workflow.py",
                "mcoi/tests/test_cognitive_shadow_observations.py",
                "mcoi/tests/test_traced_workflow.py",
                "mcoi/tests/test_server_phase199.py",
                "mcoi/tests/test_server_phase205.py",
                "mcoi/tests/test_server_phase206.py",
                "mcoi/tests/test_workflow_execution_lifecycle.py",
                "mcoi/tests/test_workflow_templates.py",
            ],
            "Workflow execution routes execute governed multi-agent workflows with action proof receipts, expose bounded history and cognitive shadow observation read models, produce replay-traced workflow runs, and record workflow lifecycle mutation receipts as bounded Effect Assurance evidence.",
            [
                "execute_workflow",
                "execute_workflow_bad_capability",
                "workflow_history",
                "read_surfaces_observations_and_summary_when_enabled",
                "read_respects_limit",
                "audit_on_success",
                "audit_on_failure",
                "workflow_runtime_error_redacted",
                "workflow_lifecycle_records_bounded_mutation_receipts",
                "workflow_failure_and_compensation_receipts_are_bounded",
                "workflow_mutation_receipt_closes_effect_assurance",
                "execute_produces_trace",
                "start_trace_failure_is_counted_and_workflow_runs",
                "complete_failure_is_counted_and_partial_trace_discarded",
                "legacy_execute_uses_request_unique_trace_witness",
                "create_session",
                "ledger_returns_entries",
                "execute_pipeline",
                "pipeline_history",
                "instantiate",
                "list_by_category",
            ],
        ),
        _surface(
            "agent_chain_execution_lifecycle",
            [
                "/api/v1/chain/execute",
                "/api/v1/chain/history",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/agent_chain.py",
                "mcoi/tests/test_agent_chain.py",
                "mcoi/tests/test_server_phase215.py",
                "mcoi/tests/test_agent_chain_execution_lifecycle.py",
            ],
            "Agent chain routes execute ordered multi-step model chains, propagate prior outputs through templates, publish bounded completion events, sanitize failure details, and expose bounded execution history.",
            [
                "chain_execute_single_step",
                "chain_execute_two_steps",
                "chain_prev_template_propagates_output",
                "chain_halt_on_failure_bounded",
                "chain_skip_on_failure_continues",
                "chain_returned_failure_redacted",
                "chain_history_bounded",
                "chain_endpoint_governed",
            ],
        ),
        _surface(
            "certification_daemon_lifecycle",
            [
                "/api/v1/daemon/force",
                "/api/v1/daemon/status",
                "/api/v1/daemon/tick",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/daemon.py",
                "mcoi/mcoi_runtime/core/certification_daemon.py",
                "mcoi/tests/test_certification_daemon.py",
                "mcoi/tests/test_server_phase200.py",
                "mcoi/tests/test_certification_daemon_lifecycle.py",
            ],
            "Certification daemon routes expose bounded daemon status, run interval-gated certification ticks, and force immediate certification runs while preserving bounded health and history state.",
            [
                "daemon_status_bounded",
                "daemon_tick_interval_gated",
                "daemon_force_runs_when_disabled",
                "daemon_force_returns_chain_hash",
                "daemon_history_bounded",
                "daemon_health_degrades_on_failures",
                "daemon_exceptions_sanitized",
                "daemon_endpoint_contracts_governed",
            ],
        ),
        _surface(
            "live_path_certification_lifecycle",
            [
                "/api/v1/certify",
                "/api/v1/certify/history",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/certify.py",
                "mcoi/mcoi_runtime/core/live_path_certification.py",
                "mcoi/tests/test_live_path_certification.py",
                "mcoi/tests/test_server_phase199.py",
                "mcoi/tests/test_e2e_integration.py",
            ],
            "Live-path certification routes run governed certification chains with action-proof receipts, step-level proof hashes, bounded failure details, deterministic chain hashes, and bounded certification history read models.",
            [
                "certification_run_emits_action_proof",
                "certification_run_returns_chain_hash",
                "certification_run_records_five_steps",
                "certification_steps_named",
                "certification_history_bounded",
                "certification_chain_hash_deterministic",
                "certification_failures_bounded",
                "certification_partial_failure_recorded",
            ],
            runtime_witness_anchor_aliases={
                "certification_run_emits_action_proof": [
                    "run_certification",
                    "workflow_then_certification",
                ],
                "certification_run_returns_chain_hash": [
                    "run_certification",
                    "all_passed",
                ],
                "certification_run_records_five_steps": [
                    "run_certification",
                    "all_passed",
                    "all_skipped",
                ],
                "certification_steps_named": [
                    "certification_steps_have_names",
                ],
                "certification_history_bounded": [
                    "certification_history",
                ],
                "certification_chain_hash_deterministic": [
                    "chain_hash_deterministic",
                ],
                "certification_failures_bounded": [
                    "failed_on_exception",
                    "exception_is_bounded",
                    "failed_on_error",
                ],
                "certification_partial_failure_recorded": [
                    "partial_failure",
                    "budget_exhaustion_during_certification",
                ],
            },
        ),
        _surface(
            "runtime_state_persistence_lifecycle",
            [
                "/api/v1/state",
                "/api/v1/state/save",
                "/api/v1/state/{state_type}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/state.py",
                "mcoi/mcoi_runtime/persistence/state_persistence.py",
                "mcoi/tests/test_state_persistence.py",
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_server_phase216.py",
            ],
            "Runtime state persistence routes save hash-bound state snapshots, load bounded state by type, reject path traversal, and expose state summary read models.",
            [
                "state_save_returns_hash_bound_snapshot",
                "state_load_roundtrip",
                "state_load_missing_bounded",
                "state_list_summary_bounded",
                "state_save_rejects_path_traversal",
                "state_load_rejects_path_traversal",
                "state_hash_mismatch_rejected",
                "state_atomic_write_verified",
            ],
            runtime_witness_anchor_aliases={
                "state_save_returns_hash_bound_snapshot": [
                    "save",
                    "save_and_load",
                    "state_hash_changes",
                ],
                "state_load_roundtrip": [
                    "save_and_load",
                    "complex_data",
                    "save_and_load",
                ],
                "state_load_missing_bounded": [
                    "load_missing",
                    "load_missing_state_returns_governed_not_found",
                ],
                "state_list_summary_bounded": [
                    "list_states",
                    "summary",
                ],
                "state_save_rejects_path_traversal": [
                    "save_rejects_path_traversal",
                    "save_rejects_invalid_state_type",
                ],
                "state_load_rejects_path_traversal": [
                    "load_rejects_path_traversal",
                    "load_rejects_invalid_state_type",
                ],
                "state_hash_mismatch_rejected": [
                    "load_rejects_hash_mismatch",
                ],
                "state_atomic_write_verified": [
                    "atomic_write",
                ],
            },
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
            "proven",
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
            runtime_witness_anchor_aliases={
                "patterns_detected_from_audit_trail": [
                    "analyze_detects_patterns",
                    "analyze_endpoint",
                ],
                "promotion_requires_detected_pattern": [
                    "promote_creates_candidate",
                    "promote_unknown_pattern_raises",
                ],
                "approval_required_before_activation": [
                    "activate_requires_approved",
                    "cannot_activate_candidate",
                    "approve_requires_candidate",
                ],
                "retirement_requires_active_runbook": [
                    "cannot_retire_non_active_runbook",
                    "cannot_retire_already_retired_runbook",
                    "retire_endpoint_rejects_non_active_runbook",
                ],
                "promote_and_approve_audit_records": [
                    "promote_creates_candidate",
                    "approve_requires_candidate",
                ],
                "mil_audit_replay_admits_runbook": [
                    "mil_audit_router_admits_replay_backed_runbook"
                ],
                "mil_audit_operator_checklist_validated": [
                    "validate_mil_audit_runbook_operator_checklist_accepts_example",
                    "validate_mil_audit_runbook_operator_checklist_rejects_missing_step",
                ],
                "mil_audit_runbook_preflight_ready": [
                    "mil_audit_runbook_preflight_accepts_valid_local_state",
                    "mil_audit_runbook_preflight_blocks_missing_record",
                ],
                "sanitized_runbook_error_details": [
                    "promote_endpoint_sanitizes_unknown_pattern",
                    "approve_endpoint_sanitizes_unknown_runbook",
                    "activate_endpoint_sanitizes_unknown_runbook",
                ],
                "runbook_pattern_read_models_bounded": [
                    "list_runbooks_endpoint",
                    "runbooks_summary_endpoint",
                ],
                "runbook_responses_governed": [
                    "list_runbooks_invalid_status_fails_closed",
                    "mil_audit_router_missing_store_fails_closed",
                ],
            },
        ),
        _surface(
            "software_outcome_learning",
            [
                "mullu_software_change",
                "_software_learning_admission_payload",
                "derive_software_outcome_learning_candidates",
                "decide_software_outcome_learning",
                "planning_knowledge_from_software_candidate",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/mcp/server.py",
                "mcoi/mcoi_runtime/contracts/software_learning.py",
                "mcoi/mcoi_runtime/core/software_learning.py",
                "mcoi/tests/test_mcp_software_change.py",
                "mcoi/tests/test_software_learning.py",
            ],
            "Software outcome learning derives sanitized procedural and risk-memory candidates from governed software-change receipts, rejects raw logs, and projects planning knowledge only after admitted learning decisions.",
            [
                "software_learning_schema_default_enabled",
                "passed_gates_yield_procedural_memory",
                "failed_gates_yield_hashed_risk_memory",
                "raw_logs_rejected_before_planning_use",
                "rollback_failure_defers_learning",
                "planning_projection_requires_admitted_matching_decision",
                "software_learning_errors_are_bounded",
            ],
            runtime_witness_anchor_aliases={
                "software_learning_schema_default_enabled": [
                    "happy_path_returns_solved_payload",
                    "learning_admission_persists_when_store_configured",
                ],
                "passed_gates_yield_procedural_memory": [
                    "derives_sanitized_procedural_and_risk_candidates",
                    "learning_decision_admits_and_projects_to_planning_knowledge",
                    "happy_path_returns_solved_payload",
                ],
                "failed_gates_yield_hashed_risk_memory": [
                    "derives_sanitized_procedural_and_risk_candidates",
                ],
                "raw_logs_rejected_before_planning_use": [
                    "raw_log_candidate_is_rejected_before_planning_use",
                    "happy_path_returns_solved_payload",
                ],
                "rollback_failure_defers_learning": [
                    "rollback_failure_defers_learning_admission",
                ],
                "planning_projection_requires_admitted_matching_decision": [
                    "planning_projection_requires_matching_admission",
                ],
                "software_learning_errors_are_bounded": [
                    "file_software_learning_store_rejects_nonfinite_json_constants",
                ],
            },
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
            [
                "receive_with_message_returns_request_receipt",
                "receive_with_message",
                "ignored_update_returns_request_receipt",
                "receive_with_command_returns_request_receipt",
            ],
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
            [
                "approve_unknown_request",
                "approve_valid_request",
                "authority_approval_chain_read_model",
                "expire_overdue_authority_approval_chains_records_transition",
                "production_approval_callback_requires_secret",
                "approval_callback_denies_unauthorized_resolver",
            ],
        ),
        _surface(
            "approval_engine_lifecycle",
            [
                "ApprovalEngine.submit_request",
                "ApprovalEngine.record_decision",
                "ApprovalEngine.consume_approval",
                "ApprovalEngine.revoke",
                "ApprovalEngine.record_override",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/core/approval.py",
                "mcoi/mcoi_runtime/contracts/approval.py",
                "mcoi/tests/test_approval.py",
            ],
            "Approval engine lifecycle mutations register request, decision, consumption, revocation, and override receipts as bounded evidence that can close Effect Assurance observation.",
            [
                "approval_request_mutation_receipt_emitted",
                "approval_decision_mutation_receipt_emitted",
                "approval_consumption_mutation_receipt_emitted",
                "approval_revocation_mutation_receipt_emitted",
                "approval_override_mutation_receipt_emitted",
                "approval_mutation_receipt_closes_effect_assurance",
            ],
            runtime_witness_anchor_aliases={
                "approval_request_mutation_receipt_emitted": [
                    "request_submission_records_bounded_receipt",
                    "approval_receipts_convert_to_effect_records",
                    "approval_mutation_receipt_closes_effect_assurance",
                ],
                "approval_decision_mutation_receipt_emitted": [
                    "decision_consumption_revocation_and_override_record_receipts",
                    "expired_decision_records_decision_receipt",
                ],
                "approval_consumption_mutation_receipt_emitted": [
                    "decision_consumption_revocation_and_override_record_receipts",
                ],
                "approval_revocation_mutation_receipt_emitted": [
                    "decision_consumption_revocation_and_override_record_receipts",
                ],
                "approval_override_mutation_receipt_emitted": [
                    "decision_consumption_revocation_and_override_record_receipts",
                ],
            },
        ),
        _surface(
            "effect_assurance_graph_commit",
            [
                "EffectAssuranceGate.commit_graph",
                "EffectAssuranceGate.graph_commit_receipts",
                "EffectAssuranceGate.graph_commit_effect_records",
                "InMemoryEffectGraphCommitReceiptStore",
                "JsonlEffectGraphCommitReceiptStore",
                "bootstrap_runtime",
                "AppConfig.effect_graph_commit_receipt_store_path",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/core/effect_assurance.py",
                "mcoi/mcoi_runtime/core/operational_graph.py",
                "mcoi/mcoi_runtime/app/bootstrap.py",
                "mcoi/mcoi_runtime/app/config.py",
                "mcoi/tests/test_effect_assurance_core.py",
                "mcoi/tests/test_bootstrap.py",
            ],
            "Effect Assurance graph commits emit bounded durable receipts for MATCH-only operational graph mutation, expose those receipts as actual effects for observation, and can be wired into runtime bootstrap through explicit configuration.",
            [
                "effect_graph_commit_requires_match",
                "effect_graph_commit_receipt_emitted",
                "effect_graph_commit_receipt_converts_to_actual_effect",
                "effect_graph_commit_receipt_closes_effect_assurance",
                "effect_graph_commit_receipt_store_replays_records",
                "bootstrap_wires_durable_effect_graph_commit_receipt_store",
            ],
            {
                "effect_graph_commit_requires_match": ["graph_commit_requires_match"],
                "effect_graph_commit_receipt_emitted": [
                    "graph_commit_writes_command_verification_and_evidence_nodes"
                ],
                "effect_graph_commit_receipt_converts_to_actual_effect": [
                    "graph_commit_receipts_convert_to_effect_records"
                ],
                "effect_graph_commit_receipt_closes_effect_assurance": [
                    "graph_commit_receipt_closes_effect_assurance"
                ],
                "effect_graph_commit_receipt_store_replays_records": [
                    "jsonl_graph_commit_receipt_store_replays_records"
                ],
                "bootstrap_wires_durable_effect_graph_commit_receipt_store": [
                    "bootstrap_runtime_wires_durable_effect_graph_commit_receipt_store"
                ],
            },
        ),
        _surface(
            "job_engine_lifecycle",
            [
                "JobEngine.create_job",
                "JobEngine.start_job",
                "JobEngine.pause_job",
                "JobEngine.resume_job",
                "JobEngine.complete_job",
                "JobEngine.fail_job",
                "JobEngine.cancel_job",
                "JobEngine.restore_job",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/core/jobs.py",
                "mcoi/mcoi_runtime/contracts/job.py",
                "mcoi/tests/test_job_core.py",
            ],
            "Job engine lifecycle mutations record create, restore, start, pause, resume, complete, fail, and cancel receipts as bounded evidence that can close Effect Assurance observation.",
            [
                "job_create_mutation_receipt_emitted",
                "job_start_mutation_receipt_emitted",
                "job_pause_resume_mutation_receipts_emitted",
                "job_terminal_mutation_receipts_emitted",
                "job_restore_mutation_receipt_emitted",
                "job_mutation_receipt_closes_effect_assurance",
            ],
            runtime_witness_anchor_aliases={
                "job_create_mutation_receipt_emitted": [
                    "lifecycle_records_bounded_mutation_receipts",
                    "job_receipts_convert_to_effect_records",
                    "job_mutation_receipt_closes_effect_assurance",
                ],
                "job_start_mutation_receipt_emitted": [
                    "lifecycle_records_bounded_mutation_receipts",
                    "pause_resume_failure_and_cancel_receipts_are_bounded",
                ],
                "job_pause_resume_mutation_receipts_emitted": [
                    "pause_resume_failure_and_cancel_receipts_are_bounded",
                ],
                "job_terminal_mutation_receipts_emitted": [
                    "lifecycle_records_bounded_mutation_receipts",
                    "pause_resume_failure_and_cancel_receipts_are_bounded",
                    "cancel_from_created",
                ],
                "job_restore_mutation_receipt_emitted": [
                    "restore_job_registers_exact_descriptor_and_state",
                ],
            },
        ),
        _surface(
            "authority_obligation_mesh",
            [
                "/authority/witness",
                "/authority/responsibility",
                "/authority/obligations",
                "/authority/escalations",
                "/commands/{command_id}/authority",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/server.py",
                "gateway/authority_obligation_mesh.py",
                "tests/test_gateway/test_webhooks.py",
                "tests/test_gateway/test_authority_obligation_mesh.py",
            ],
            "Authority and obligation surfaces expose unresolved responsibility state.",
            [
                "pending_approval_chain_count",
                "open_obligation_count",
                "overdue_obligation_count",
                "escalated_obligation_count",
                "command_authority_read_model_bound_to_approval_chain",
            ],
            runtime_witness_anchor_aliases={
                "pending_approval_chain_count": [
                    "prepare_authority_binds_ownership_and_pending_approval_chain",
                    "authority_approval_chain_read_model",
                    "authority_witness_read_model",
                ],
                "open_obligation_count": [
                    "review_terminal_certificate_opens_owned_obligation_and_escalates_when_overdue",
                    "authority_obligation_and_escalation_read_models",
                    "authority_witness_read_model",
                ],
                "overdue_obligation_count": [
                    "review_terminal_certificate_opens_owned_obligation_and_escalates_when_overdue",
                    "authority_obligation_and_escalation_read_models",
                ],
                "escalated_obligation_count": [
                    "review_terminal_certificate_opens_owned_obligation_and_escalates_when_overdue",
                    "escalate_overdue_authority_obligations_records_transition",
                ],
                "command_authority_read_model_bound_to_approval_chain": [
                    "authority_approval_chain_read_model",
                    "authority_obligation_and_escalation_read_models",
                ],
            },
        ),
        _surface(
            "authority_operator_controls",
            [
                "/authority/operator",
                "/authority/operator-audit",
                "/authority/ownership",
                "/authority/policies",
                "/authority/approval-chains/expire-overdue",
                "/authority/approval-chains/close-expired",
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
            "Authority operator controls bind guarded operator access, audit events, ownership and policy read models, overdue approval expiration, expired approval closure, and obligation satisfaction/escalation controls.",
            [
                "operator_access_guard",
                "operator_audit_events",
                "ownership_policy_read_models",
                "approval_expiration_witness",
                "expired_approval_chain_closure_witness",
                "obligation_satisfaction_escalation_witness",
            ],
            runtime_witness_anchor_aliases={
                "operator_access_guard": [
                    "authority_operator_secret_required_in_production",
                    "authority_operator_identity_role_allowed_in_production",
                    "authority_operator_identity_role_denied_in_production",
                ],
                "operator_audit_events": [
                    "authority_operator_audit_read_model",
                    "authority_operator_secret_required_in_production",
                ],
                "ownership_policy_read_models": [
                    "authority_ownership_read_model_filters_owner_records",
                    "authority_policy_read_model_filters_approval_and_escalation_policies",
                ],
                "approval_expiration_witness": [
                    "expire_overdue_authority_approval_chains_records_transition",
                    "overdue_approval_chain_expires_when_command_ledger_lost_state",
                    "overdue_approval_chain_expires_and_emits_escalation_event",
                ],
                "expired_approval_chain_closure_witness": [
                    "close_expired_authority_approval_chains_clears_debt",
                    "expired_approval_chain_closure_clears_active_debt",
                ],
                "obligation_satisfaction_escalation_witness": [
                    "authority_obligation_and_escalation_read_models",
                    "authority_obligation_satisfaction_rejects_missing_obligation",
                    "escalate_overdue_authority_obligations_records_transition",
                    "satisfy_obligation_requires_evidence_and_active_status",
                ],
            },
        ),
        _surface(
            "oidc_jwks_refresh_evidence",
            [
                "OidcJwksRefreshEvidence",
                "OidcJwksRefreshAssessment",
                "assess_oidc_jwks_refresh_evidence",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/tenant_identity.py",
                "docs/54_authority_directory_sync.md",
                "examples/sdlc/requirement_oidc_jwks_refresh_evidence_20260615.json",
                "examples/sdlc/design_oidc_jwks_refresh_evidence_20260615.json",
                "examples/sdlc/security_review_oidc_jwks_refresh_evidence_20260615.json",
                "tests/test_gateway/test_tenant_identity.py",
            ],
            "OIDC/JWKS refresh evidence is a proof-only trust-chain witness that accepts only HTTPS, issuer-pinned, audience-bound, JWKS-backed, hash-retained, fresh-cache receipts and never authenticates requests or fetches network metadata.",
            [
                "fresh_https_jwks_receipt_accepted",
                "stale_cache_and_missing_refs_blocked",
                "insecure_discovery_and_redirects_blocked",
                "invalid_hashes_and_algorithms_blocked",
                "non_boolean_boundary_flags_rejected",
                "jwks_refresh_supports_trusted_header_admission",
            ],
            runtime_witness_anchor_aliases={
                "fresh_https_jwks_receipt_accepted": [
                    "oidc_jwks_refresh_evidence_accepts_fresh_https_receipt",
                ],
                "stale_cache_and_missing_refs_blocked": [
                    "oidc_jwks_refresh_evidence_blocks_stale_cache_and_missing_refs",
                ],
                "insecure_discovery_and_redirects_blocked": [
                    "oidc_jwks_refresh_evidence_blocks_insecure_discovery_and_redirects",
                ],
                "invalid_hashes_and_algorithms_blocked": [
                    "oidc_jwks_refresh_evidence_blocks_invalid_hashes_and_algorithms",
                ],
                "non_boolean_boundary_flags_rejected": [
                    "oidc_jwks_refresh_evidence_rejects_non_boolean_boundary_flags",
                ],
                "jwks_refresh_supports_trusted_header_admission": [
                    "trusted_identity_headers_accept_oidc_refresh_assessment_evidence",
                ],
            },
        ),
        _surface(
            "trusted_identity_header_boundary",
            [
                "TrustedIdentityGatewayEvidence",
                "TrustedIdentityHeaderBoundaryAssessment",
                "assess_trusted_identity_header_boundary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/tenant_identity.py",
                "docs/54_authority_directory_sync.md",
                "examples/sdlc/requirement_trusted_identity_header_boundary_20260615.json",
                "examples/sdlc/design_trusted_identity_header_boundary_20260615.json",
                "examples/sdlc/security_review_trusted_identity_header_boundary_20260615.json",
                "tests/test_gateway/test_tenant_identity.py",
            ],
            "Trusted identity headers remain disabled by default and are accepted only when an upstream gateway proves client-header stripping, verified injection, OIDC/JWKS or mTLS verification, rollback or bypass protection, and retained evidence refs.",
            [
                "trusted_headers_disabled_by_default",
                "complete_oidc_gateway_evidence_accepted",
                "complete_mtls_gateway_evidence_accepted",
                "missing_gateway_evidence_blocked",
                "malformed_evidence_refs_rejected",
                "non_boolean_gateway_evidence_rejected",
                "jwks_refresh_assessment_binds_trusted_header_path",
            ],
            runtime_witness_anchor_aliases={
                "trusted_headers_disabled_by_default": [
                    "trusted_identity_headers_disabled_by_default",
                ],
                "complete_oidc_gateway_evidence_accepted": [
                    "trusted_identity_headers_accept_complete_oidc_gateway_evidence",
                ],
                "complete_mtls_gateway_evidence_accepted": [
                    "trusted_identity_headers_accept_complete_mtls_gateway_evidence",
                ],
                "missing_gateway_evidence_blocked": [
                    "trusted_identity_headers_block_missing_gateway_evidence",
                ],
                "malformed_evidence_refs_rejected": [
                    "trusted_identity_headers_reject_malformed_evidence_refs",
                ],
                "non_boolean_gateway_evidence_rejected": [
                    "trusted_identity_headers_reject_non_boolean_evidence",
                ],
                "jwks_refresh_assessment_binds_trusted_header_path": [
                    "trusted_identity_headers_accept_oidc_refresh_assessment_evidence",
                ],
            },
        ),
        _surface(
            "orgos_case_governance_lifecycle",
            [
                "/api/v1/orgs",
                "/api/v1/orgs/{org_id}/action-queue",
                "/api/v1/orgs/{org_id}/action-queue/approval-packet-preview",
                "/api/v1/orgs/{org_id}/action-queue/dispatch-lease-preview",
                "/api/v1/orgs/{org_id}/action-queue/selection-preview",
                "/api/v1/orgs/{org_id}/action-queue/worker-dispatch-receipt",
                "/api/v1/orgs/{org_id}/action-queue/worker-lease",
                "/api/v1/orgs/{org_id}/action-queue/view",
                "/api/v1/orgs/{org_id}/authority-map",
                "/api/v1/orgs/{org_id}/authority-map/view",
                "/api/v1/orgs/{org_id}/bootstrap-minimum",
                "/api/v1/orgs/{org_id}/case-portfolio",
                "/api/v1/orgs/{org_id}/case-portfolio/view",
                "/api/v1/orgs/{org_id}/department-registry",
                "/api/v1/orgs/{org_id}/department-registry/view",
                "/api/v1/orgs/{org_id}/departments",
                "/api/v1/departments",
                "/api/v1/cases",
                "/api/v1/cases/launch-gateway-pilot",
                "/api/v1/cases/{case_id}",
                "/api/v1/cases/{case_id}/approvals",
                "/api/v1/cases/{case_id}/audit-explorer",
                "/api/v1/cases/{case_id}/audit-explorer/view",
                "/api/v1/cases/{case_id}/closure-certificate",
                "/api/v1/cases/{case_id}/closure-certificate/view",
                "/api/v1/cases/{case_id}/closure-drift-remediation-actions",
                "/api/v1/cases/{case_id}/closure-drift-remediations",
                "/api/v1/cases/{case_id}/events",
                "/api/v1/cases/{case_id}/evidence",
                "/api/v1/cases/{case_id}/learning-admissions",
                "/api/v1/cases/{case_id}/proof-explorer",
                "/api/v1/cases/{case_id}/proof-explorer/view",
                "/api/v1/cases/{case_id}/proof-timeline",
                "/api/v1/cases/{case_id}/step-handoffs",
                "/api/v1/cases/{case_id}/step-handoffs/view",
                "/api/v1/cases/{case_id}/launch-gateway-pilot/deployment-witness",
                "/api/v1/cases/{case_id}/launch-gateway-pilot/gate-preview",
                "/api/v1/cases/{case_id}/launch-gateway-pilot/readiness",
                "/api/v1/cases/{case_id}/launch-gateway-pilot/readiness-closure",
                "/api/v1/cases/{case_id}/plan",
                "/api/v1/cases/{case_id}/plan-steps/{step_id}/admission-preview",
                "/api/v1/cases/{case_id}/plan-steps/{step_id}/gate",
                "/api/v1/cases/{case_id}/plan-steps/{step_id}/private-pilot/rehearsal",
                "/api/v1/cases/{case_id}/plan-steps/{step_id}/worker-receipt",
                "/api/v1/cases/{case_id}/close",
                "/api/v1/orgos/read-model",
                "/api/v1/orgos/replay",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/server.py",
                "gateway/orgos_kernel.py",
                "mcoi/mcoi_runtime/app/routers/organization_kernel.py",
                "mcoi/mcoi_runtime/core/organization_kernel.py",
                "mcoi/mcoi_runtime/persistence/organization_kernel_store.py",
                "tests/test_gateway/test_orgos_api.py",
                "tests/test_gateway/test_orgos_kernel.py",
                "mcoi/tests/test_organization_kernel.py",
                "mcoi/tests/test_organization_kernel_router.py",
                "mcoi/tests/test_organization_kernel_store.py",
            ],
            "OrgOS lifecycle routes register organization authority, departments, governed cases, evidence events, plan gates, action-admission previews, action queue selection previews, action queue approval packet previews, action queue dispatch lease previews, worker lease creation receipts, worker dispatch request receipts, private pilot live rehearsal receipts, closure decisions that must carry the latest admitted gate evidence refs, post-closure drift remediation routing, policy-checked operator remediation actions, case portfolio, action queue, authority-map and department-registry views, terminal certificate views with missing gate-evidence attention details, replayed read models, proof timelines, audit explorer projections, proof explorer projections, step handoff projections, browser-facing proof views, and bounded worker output receipts that require matching dispatch receipts before plan-step evidence admission.",
            [
                "orgos_api_runs_launch_gateway_case_control_loop",
                "orgos_api_denies_unbound_authority_gate",
                "orgos_api_org_registration_rolls_back_invalid_authority_bundle",
                "orgos_api_replays_projection_from_jsonl_event_log",
                "orgos_kernel_bootstraps_five_departments_and_launch_gateway_case",
                "orgos_kernel_rejects_ownerless_authority_and_tenant_mismatch",
                "plan_step_gate_denies_missing_authority_capability_evidence_and_world_refs",
                "plan_step_gate_denies_cross_tenant_or_unbound_authority",
                "plan_step_gate_allows_certified_authorized_gateway_step",
                "case_closure_requires_effect_reconciliation_match_for_committed",
                "terminal_closure_requires_latest_gate_evidence_refs",
                "terminal_closure_requires_worker_bound_gate_evidence_refs",
                "closure_certificate_reports_required_gate_evidence_before_closure",
                "case_proof_explorer_reports_open_case_attention_without_mutation",
                "case_proof_explorer_reports_closed_verified_case",
                "case_proof_explorer_html_view_is_read_only_and_escaped",
                "authority_map_view_is_read_only_escaped_and_chained",
                "case_audit_explorer_reports_open_case_without_mutation",
                "case_audit_explorer_view_is_read_only_and_escaped",
                "case_portfolio_view_is_read_only_escaped_and_grouped",
                "case_portfolio_reports_closed_verified_case",
                "case_step_handoffs_report_worker_receipt_binding_without_mutation",
                "case_step_handoffs_view_is_read_only_and_escaped",
                "case_plan_step_admission_preview_defers_missing_evidence_without_mutation",
                "case_plan_step_admission_preview_allows_receipt_binding_without_dispatch",
                "organization_action_queue_reports_deferred_handoff_actions_without_mutation",
                "organization_action_queue_reports_receipt_ready_step_without_dispatch",
                "organization_action_queue_filters_ready_receipt_actions_without_mutation",
                "organization_action_queue_selection_preview_simulates_visible_filtered_action_without_mutation",
                "organization_action_queue_selection_preview_rejects_filtered_out_action_without_mutation",
                "organization_action_queue_approval_packet_preview_defers_missing_evidence_without_mutation",
                "organization_action_queue_approval_packet_preview_requires_approval_after_evidence_ready",
                "organization_action_queue_approval_packet_preview_rejects_filtered_out_action_without_mutation",
                "organization_action_queue_dispatch_lease_preview_reports_ready_lease_without_dispatch",
                "organization_action_queue_dispatch_lease_preview_simulates_missing_evidence_without_mutation",
                "organization_action_queue_dispatch_lease_preview_blocks_until_approval_without_mutation",
                "organization_action_queue_dispatch_lease_preview_rejects_filtered_out_action_without_mutation",
                "organization_action_queue_worker_lease_creates_receipt_without_dispatch",
                "organization_action_queue_worker_lease_rejects_not_ready_selection_without_mutation",
                "organization_action_queue_worker_lease_rejects_duplicate_lease_without_extra_event",
                "organization_action_queue_worker_dispatch_receipt_records_envelope_without_output_binding",
                "organization_action_queue_worker_dispatch_receipt_rejects_missing_lease_without_mutation",
                "organization_action_queue_worker_dispatch_receipt_rejects_duplicate_dispatch_without_extra_event",
                "organization_action_queue_worker_dispatch_receipt_rejects_not_ready_selection_without_mutation",
                "organization_action_queue_view_is_read_only_and_escaped",
                "case_private_pilot_live_rehearsal_binds_preview_receipts_without_mutation",
                "organization_action_queue_view_preserves_filters",
                "department_registry_view_is_read_only_and_escaped",
                "case_closure_certificate_view_is_read_only_and_escaped",
                "closed_case_reports_closure_packet_drift_after_gate_refresh",
                "closure_packet_drift_accepts_remediation_routing",
                "closure_packet_drift_remediation_rejects_mismatched_refs",
                "closure_packet_drift_operator_actions_report_policy_requirements",
                "closure_packet_drift_operator_action_binds_review_remediation",
                "closure_packet_drift_operator_action_rejects_missing_policy_evidence",
                "case_proof_timeline_reports_open_case_without_closure",
                "case_proof_timeline_reports_closure_certificate_and_learning",
                "learning_binding_requires_closed_case_and_admission_decision",
                "launch_gateway_pilot_collects_deployment_witness_and_allows_engineering_gate",
                "launch_gateway_pilot_gate_preview_is_non_mutating",
                "launch_gateway_pilot_gate_preview_allows_without_writing_decisions",
                "launch_gateway_pilot_readiness_read_model_reports_missing_evidence",
                "launch_gateway_pilot_readiness_packet_closes_after_verified_witness",
                "launch_gateway_pilot_readiness_packet_blocks_without_engineering_witness",
                "jsonl_case_event_log_preserves_hash_chain",
                "worker_receipts_satisfy_engineering_gate_evidence",
                "worker_receipt_requires_recorded_dispatch_receipt",
                "worker_receipt_rejects_dispatch_identity_mismatch",
                "worker_receipt_endpoint_rejects_missing_dispatch_receipt",
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
                ".github/workflows/deployment-witness.yml",
                "scripts/orchestrate_deployment_witness.py",
                "scripts/preflight_deployment_witness.py",
                "scripts/collect_deployment_witness.py",
                "scripts/emit_gateway_dns_target_binding_receipt.py",
                "scripts/validate_gateway_dns_target_binding_receipt.py",
                "scripts/emit_deployment_upstream_blocker_receipt.py",
                "scripts/validate_deployment_upstream_blocker_receipt.py",
                "scripts/collect_gateway_dns_resolution_receipt.py",
                "scripts/validate_deployment_publication_closure.py",
                "scripts/apply_deployment_publication_status.py",
                "scripts/validate_mcp_capability_manifest.py",
                "scripts/validate_mcp_operator_checklist.py",
                "scripts/validate_gateway_publication_receipt.py",
                "scripts/validate_deployment_orchestration_receipt.py",
                "scripts/validate_gateway_dns_resolution_receipt.py",
                "schemas/deployment_publication_closure_validation.schema.json",
                "schemas/public_production_health_declaration.schema.json",
                "schemas/deployment_orchestration_receipt.schema.json",
                "schemas/deployment_orchestration_receipt_validation.schema.json",
                "schemas/gateway_dns_target_binding_receipt.schema.json",
                "schemas/deployment_upstream_blocker_receipt.schema.json",
                "schemas/gateway_dns_resolution_receipt.schema.json",
                "schemas/gateway_publication_readiness.schema.json",
                "schemas/gateway_publication_receipt_validation.schema.json",
                "schemas/deployment_witness.schema.json",
                "schemas/latest_anchor_read_model.schema.json",
                "schemas/runtime_witness.schema.json",
                "schemas/mullu_governance_protocol.manifest.json",
                "tests/test_gateway/test_webhooks.py",
                "tests/test_orchestrate_deployment_witness.py",
                "tests/test_emit_gateway_dns_target_binding_receipt.py",
                "tests/test_validate_gateway_dns_target_binding_receipt.py",
                "tests/test_emit_deployment_upstream_blocker_receipt.py",
                "tests/test_validate_deployment_upstream_blocker_receipt.py",
                "tests/test_collect_gateway_dns_resolution_receipt.py",
                "tests/test_report_gateway_publication_readiness.py",
                "tests/test_validate_gateway_dns_resolution_receipt.py",
                "tests/test_validate_gateway_publication_receipt.py",
                "tests/test_validate_deployment_orchestration_receipt.py",
                "tests/test_validate_deployment_publication_closure.py",
                "tests/test_apply_deployment_publication_status.py",
                "tests/test_validate_protocol_manifest.py",
                "tests/test_preflight_deployment_witness.py",
                "tests/test_collect_deployment_witness.py",
                "tests/test_validate_deployment_publication_closure.py",
            ],
            "Runtime witness surfaces publish bounded operational and responsibility debt state; deployment witnesses require raw runtime and authority debt-clear evidence before publication closure, DNS receipts bind host resolution state before endpoint publication, public-health status mutation requires a matching published witness plus operator approval, and orchestration receipts bind ingress render, MCP checklist validation, preflight, dispatch evidence, schema contract validation, and post-run receipt validation before deployment witness readiness.",
            [
                "gateway_witness",
                "runtime_witness_alias",
                "latest_anchor_read_model",
                "runtime_self_reflex_read_models_do_not_mutate",
                "collect_deployment_witness_publishes_with_verified_signature",
                "collect_deployment_witness_rejects_responsibility_debt",
                "collect_deployment_witness_rejects_runtime_responsibility_debt",
                "preflight_deployment_witness_rejects_responsibility_debt",
                "preflight_deployment_witness_rejects_runtime_witness_responsibility_debt",
                "published_status_rejects_authority_responsibility_debt",
                "published_status_rejects_runtime_responsibility_debt",
                "orchestrate_deployment_witness_renders_and_provisions",
                "orchestration_receipt_schema_matches_cli_output",
                "orchestration_validation_report_matches_public_schema",
                "gateway_dns_target_binding_receipt_matches_public_schema",
                "gateway_dns_target_binding_validation_report_writes_bounded_result",
                "deployment_upstream_blocker_receipt_matches_public_schema",
                "deployment_upstream_blocker_validation_accepts_ready_receipt",
                "gateway_dns_resolution_receipt_matches_public_schema",
                "gateway_dns_receipt_validation_report_writes_bounded_result",
                "closure_validation_report_matches_public_schema_for_not_published",
                "readiness_report_matches_public_schema",
                "receipt_validation_report_matches_public_schema",
                "protocol_manifest_indexes_deployment_orchestration_validation",
                "protocol_manifest_indexes_deployment_publication_closure_validation",
                "protocol_manifest_indexes_public_production_health_declaration",
                "protocol_manifest_indexes_gateway_publication_readiness",
                "protocol_manifest_indexes_gateway_dns_target_binding_receipt",
                "protocol_manifest_indexes_deployment_upstream_blocker_receipt",
                "protocol_manifest_indexes_gateway_dns_resolution_receipt",
                "protocol_manifest_indexes_gateway_publication_receipt_validation",
                "protocol_manifest_indexes_runtime_witness_and_latest_anchor",
                "apply_deployment_publication_status_updates_verified_claim",
                "apply_deployment_publication_status_blocks_missing_approval",
                "apply_deployment_publication_status_blocks_unpublished_witness",
                "apply_deployment_publication_status_writes_receipt",
                "published_status_report_accepts_declaration_receipt",
                "published_status_report_rejects_dry_run_declaration_receipt",
            ],
        ),
        _surface(
            "runtime_conformance_attestation",
            ["/runtime/conformance"],
            "read_model",
            "read_model",
            "audit_chain",
            "proven",
            [
                "gateway/server.py",
                "gateway/conformance.py",
                ".github/workflows/deployment-witness.yml",
                "gateway/physical_worker_canary.py",
                "scripts/collect_runtime_conformance.py",
                "scripts/produce_physical_worker_canary.py",
                "scripts/validate_mcp_capability_manifest.py",
                "tests/test_validate_release_status.py",
                "tests/test_validate_public_repository_surface.py",
                "schemas/runtime_conformance_certificate.schema.json",
                "schemas/runtime_conformance_collection.schema.json",
                "tests/test_gateway/test_conformance.py",
                "tests/test_gateway/test_webhooks.py",
                "tests/test_gateway/test_physical_worker_canary.py",
                "mcoi/tests/test_server_lineage.py",
                "tests/test_collect_runtime_conformance.py",
                "tests/test_produce_physical_worker_canary.py",
            ],
            "Runtime conformance certificate binds live witness, closure, fabric, isolation, lineage, authority, physical worker canary proof, MCP manifest validity, proof-matrix route classification summary, document-drift checks, issuer schema self-validation, and collector schema validation into one signed attestation.",
            [
                "runtime_conformance_endpoint_returns_signed_gap_certificate",
                "runtime_witness_endpoints_match_public_schema",
                "runtime_conformance_certificate_matches_schema",
                "isolation_canary_passes_locally_without_worker",
                "isolation_canary_fails_closed_when_worker_unconfigured",
                "isolation_canary_requires_live_isolated_worker_receipt",
                "collect_runtime_conformance_rejects_schema_invalid_certificate",
                "runtime_conformance_surfaces_unclassified_proof_routes",
                "collect_runtime_conformance_rejects_failed_core_canary",
                "command_capability_admission_read_model_reports_accepted_witness",
                "fabric_admission_blocks_uninstalled_runtime_intent",
                "lineage_resolve_route_returns_trace_document",
                "collect_runtime_conformance_rejects_unclear_responsibility_debt",
                "runtime_conformance_accepts_valid_authority_directory_sync_receipt",
                "runtime_conformance_witnesses_capability_plan_bundle",
                "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay",
                "physical_worker_canary_evidence_and_hash_are_stable",
                "deployment_witness_workflow_carries_conformance_secret_handoff",
                "deployment_witness_workflow_requires_conformance_secret_handoff",
                "write_runtime_conformance_persists_json",
                "write_runtime_conformance_rejects_collection_schema_drift",
            ],
        ),
        _surface(
            "proof_route_gap_triage",
            [
                "build_gap_triage_report",
                "discover_route_declarations",
                ".change_assurance/proof_route_gap_triage.json",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "scripts/proof_route_gap_triage.py",
                "tests/test_proof_route_gap_triage.py",
                "docs/70_proof_route_gap_triage.md",
            ],
            "Proof-route gap triage ranks unclassified declared routes by family, source file, method, and effect risk without reclassifying any route, producing a deterministic closure queue for the proof matrix.",
            [
                "unclassified_routes_grouped_by_family",
                "route_gap_triage_binds_source_files_and_methods",
                "closure_candidates_ranked_deterministically",
                "triage_report_check_detects_stale_output",
            ],
        ),
        _surface(
            "production_evidence_plane",
            [
                "/health",
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
                "schemas/gateway_health.schema.json",
                "schemas/production_evidence_witness.schema.json",
                "schemas/capability_evidence_endpoint.schema.json",
                "schemas/audit_verification_endpoint.schema.json",
                "schemas/proof_verification_endpoint.schema.json",
                "tests/test_gateway/test_production_evidence.py",
                "tests/test_collect_deployment_witness.py",
            ],
            "Production evidence endpoints expose signed deployment posture, capability evidence, audit verification, and proof verification; deployment witness collection can require the whole plane before publication, derives live physical safety evidence only from certified registry extensions, and blocks live physical capability claims without explicit safety evidence while allowing sandbox-only physical canary evidence.",
            [
                "gateway_health_schema_valid",
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
            runtime_witness_anchor_aliases={
                "gateway_health_schema_valid": [
                    "gateway_health_matches_public_schema"
                ],
                "signed_production_evidence_witness": [
                    "deployment_witness_is_signed_and_reports_missing_runtime_evidence",
                    "collect_deployment_witness_publishes_with_verified_signature",
                ],
                "capability_evidence_schema_valid": [
                    "capabilities_evidence_reports_disabled_registry"
                ],
                "audit_verification_schema_valid": [
                    "audit_and_proof_verify_surface_anchor_gap"
                ],
                "proof_verification_schema_valid": [
                    "audit_and_proof_verify_surface_anchor_gap"
                ],
                "deployment_collection_requires_production_evidence": [
                    "collect_deployment_witness_requires_production_evidence_plane"
                ],
                "live_physical_safety_evidence_derived_from_registry": [
                    "live_physical_capability_evidence_is_derived_from_registry_extension"
                ],
                "live_physical_capability_requires_safety_evidence": [
                    "collect_deployment_witness_rejects_live_physical_capability_without_safety_evidence",
                    "physical_capability_policy_blocks_live_physical_without_safety_evidence",
                    "live_physical_capability_without_registry_safety_refs_remains_blocked",
                ],
                "sandbox_physical_capability_remains_non_production": [
                    "physical_capability_policy_allows_sandbox_only_physical_capability",
                    "collect_deployment_witness_allows_sandbox_physical_capability_without_live_claim",
                ],
                "missing_production_evidence_fails_closed": [
                    "collect_deployment_witness_rejects_missing_production_evidence_secret",
                    "collect_deployment_witness_fails_closed_without_secret",
                ],
            },
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
            runtime_witness_anchor_aliases={
                "operator_only_access": [
                    "reflex_health_and_inspect_are_operator_guarded_local",
                    "reflex_endpoints_fail_closed_without_operator_in_production",
                ],
                "mutation_applied_false": [
                    "reflex_diagnose_evaluate_and_propose_are_non_mutating",
                    "runtime_self_reflex_read_models_do_not_mutate",
                    "reflex_certification_handoff_is_non_mutating_and_cli_ready",
                ],
                "certification_handoff_required": [
                    "reflex_certify_returns_handoff_not_self_certificate",
                    "reflex_certification_handoff_is_non_mutating_and_cli_ready",
                ],
                "protected_surfaces_auto_promote_false": [
                    "upgrade_planner_blocks_protected_surfaces_from_auto_promotion",
                    "protected_candidate_canary_handoff_routes_to_human_approval",
                    "reflex_candidate_builds_governed_change_command_for_protected_surface",
                ],
                "signed_reflex_witness": [
                    "reflex_deployment_witness_verifier_accepts_signed_witness",
                    "validate_reflex_deployment_witness_accepts_signed_witness",
                    "reflex_witness_is_signed_and_binds_pipeline_counts",
                ],
                "reflex_deployment_witness_schema": [
                    "reflex_deployment_witness_envelope_schema_accepts_fixture",
                    "validate_reflex_deployment_witness_rejects_schema_violation",
                ],
                "reflex_validator_receipt_schema": [
                    "reflex_validator_receipt_schema_accepts_passing_receipt",
                    "reflex_validator_receipt_schema_accepts_failed_receipt",
                ],
                "offline_reflex_witness_replay": [
                    "validate_reflex_deployment_witness_accepts_export_envelope",
                    "reflex_deployment_witness_query_returns_replay_status",
                    "reflex_sandbox_bundle_runs_declared_replays_without_side_effects",
                ],
                "reflex_validator_receipt_artifact": [
                    "reflex_validator_receipt_accepts_passing_junit",
                    "reflex_validator_receipt_cli_writes_json",
                ],
            },
        ),
        _surface(
            "governed_operational_intelligence",
            [
                "WorldStateStore.add_entity",
                "project_repository_observation_packet_to_world_state",
                "bind_repository_world_state_projection_to_problem_star_evidence",
                "GoalCompiler.compile",
                "CausalSimulator.simulate",
                "/api/v1/knowledge/entities",
                "/api/v1/knowledge/links",
                "/api/v1/knowledge/entities/{entity_id}/links",
                "/api/v1/knowledge/contradictions",
                "/api/v1/knowledge/contradictions/unresolved",
                "/api/v1/knowledge/summary",
                "/api/v1/simulate",
                "/api/v1/simulate/history",
                "/api/v1/simulate/summary",
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
                "mcoi/mcoi_runtime/app/routers/knowledge.py",
                "mcoi/mcoi_runtime/app/routers/simulation.py",
                "mcoi/mcoi_runtime/core/knowledge_graph.py",
                "mcoi/mcoi_runtime/governance/policy/sandbox.py",
                "schemas/world_state.schema.json",
                "schemas/goal.schema.json",
                "schemas/simulation_receipt.schema.json",
                "mcoi/tests/test_knowledge_graph.py",
                "mcoi/tests/test_policy_sandbox.py",
                "tests/test_gateway/test_world_state.py",
                "tests/test_gateway/test_goal_compiler.py",
                "tests/test_gateway/test_causal_simulator.py",
            ],
            "Governed operational intelligence binds sourced world-state admission, repository observation packet projection, planning-only ProblemStar evidence binding, knowledge graph entity/link/contradiction routes, policy simulation dry-run APIs, compiled goal-plan certificates, and deterministic causal simulation receipts before effect-bearing execution.",
            [
                "world_assertions_require_source_evidence",
                "repository_observation_packets_project_to_world_state",
                "repository_world_state_projection_binds_problem_star_evidence",
                "repository_world_state_projection_blocks_problem_star_evidence",
                "repository_observation_failures_block_world_state_planning",
                "foundation_repository_observation_blocks_without_contradiction",
                "knowledge_entity_routes_governed",
                "knowledge_link_routes_governed",
                "knowledge_contradiction_routes_governed",
                "knowledge_summary_route_bounded",
                "policy_simulation_routes_governed",
                "policy_simulation_history_summary_bounded",
                "goal_plan_certificate_hash_bound",
                "simulation_receipt_schema_valid",
                "open_world_contradictions_block_execution",
                "high_risk_controls_projected_before_execution",
            ],
            runtime_witness_anchor_aliases={
                "world_assertions_require_source_evidence": [
                    "world_state_store_rejects_unsourced_assertion",
                    "world_state_schema_rejects_entity_without_evidence",
                ],
                "repository_observation_packets_project_to_world_state": [
                    "repository_observation_packet_projects_to_world_state_planning_claims",
                ],
                "repository_world_state_projection_binds_problem_star_evidence": [
                    "repository_world_state_projection_binds_problem_star_evidence",
                ],
                "repository_world_state_projection_blocks_problem_star_evidence": [
                    "repository_world_state_projection_blocks_problem_star_evidence_on_contradiction",
                    "foundation_repository_world_state_projection_blocks_problem_star_evidence",
                ],
                "repository_observation_failures_block_world_state_planning": [
                    "repository_observation_command_failure_projects_open_contradiction",
                ],
                "foundation_repository_observation_blocks_without_contradiction": [
                    "foundation_repository_observation_projection_blocks_without_contradiction",
                ],
                "knowledge_entity_routes_governed": [
                    "add_entity_endpoint",
                    "query_entities_endpoint",
                    "query_entities_invalid_type_fails_closed_without_leakage",
                ],
                "knowledge_link_routes_governed": ["add_link_endpoint"],
                "knowledge_contradiction_routes_governed": [
                    "contradiction_endpoints_emit_governed_read_model"
                ],
                "knowledge_summary_route_bounded": ["knowledge_summary_endpoint"],
                "policy_simulation_routes_governed": ["simulate_endpoint"],
                "policy_simulation_history_summary_bounded": [
                    "simulation_history_endpoint",
                    "simulation_summary_endpoint",
                    "history_bounded",
                ],
                "goal_plan_certificate_hash_bound": [
                    "goal_compiler_compiles_high_risk_payment_with_controls",
                    "goal_schema_accepts_compiled_goal_plan",
                ],
                "simulation_receipt_schema_valid": [
                    "simulation_receipt_schema_accepts_dry_run_receipt"
                ],
                "open_world_contradictions_block_execution": [
                    "causal_simulator_blocks_open_world_contradictions",
                    "world_state_contradiction_blocks_planning_and_execution_claims",
                ],
                "high_risk_controls_projected_before_execution": [
                    "causal_simulator_projects_high_risk_controls",
                    "goal_compiler_compiles_high_risk_payment_with_controls",
                ],
            },
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
            "Capability forge emits schema-backed candidate packages and maturity-ready certification handoffs only, keeps promotion blocked, validates approval, sandbox, receipt, eval, live-write, physical safety, and recovery evidence before certification handoff, installs certified handoffs as certification and physical safety evidence without direct maturity overrides, and batches handoff evidence with exact capsule-entry coverage before registry admission.",
            [
                "candidate_promotion_blocked",
                "candidate_schema_valid",
                "candidate_certification_handoff_emits_maturity_bundle",
                "certification_handoff_installs_evidence_without_maturity_claim",
                "certification_handoff_batch_preserves_capsule_admission_gate",
                "physical_candidate_declares_live_safety_evidence_requirements",
                "physical_handoff_installs_live_safety_evidence",
                "high_risk_approval_policy_required",
                "effect_bearing_candidate_requires_sandbox",
                "effect_bearing_candidate_requires_recovery_path",
            ],
            runtime_witness_anchor_aliases={
                "candidate_promotion_blocked": [
                    "capability_forge_rejects_candidate_self_promotion",
                    "capability_candidate_schema_rejects_unblocked_candidate",
                ],
                "candidate_schema_valid": [
                    "capability_forge_creates_schema_valid_candidate_package"
                ],
                "candidate_certification_handoff_emits_maturity_bundle": [
                    "capability_forge_builds_certification_handoff_for_maturity_synthesis"
                ],
                "certification_handoff_installs_evidence_without_maturity_claim": [
                    "capability_forge_installs_handoff_as_certification_evidence_only"
                ],
                "certification_handoff_batch_preserves_capsule_admission_gate": [
                    "capability_forge_installs_handoff_evidence_batch_with_audit_hash",
                    "capability_forge_handoff_batch_rejects_coverage_drift",
                    "capability_forge_handoff_install_rejects_gate_bypasses",
                ],
                "physical_candidate_declares_live_safety_evidence_requirements": [
                    "capability_forge_generates_physical_safety_evidence_requirements",
                    "capability_forge_rejects_physical_candidate_missing_safety_requirement",
                ],
                "physical_handoff_installs_live_safety_evidence": [
                    "capability_forge_installs_physical_safety_refs_from_handoff"
                ],
                "high_risk_approval_policy_required": [
                    "capability_forge_projects_high_risk_controls",
                    "capability_forge_certification_handoff_rejects_missing_required_refs",
                ],
                "effect_bearing_candidate_requires_sandbox": [
                    "capability_forge_certification_handoff_rejects_missing_required_refs",
                    "capability_forge_rejects_missing_required_eval",
                ],
                "effect_bearing_candidate_requires_recovery_path": [
                    "capability_forge_rejects_effect_bearing_package_without_recovery"
                ],
            },
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
                "operator_console_links_capability_improvement_portfolio",
                "capability_maturity_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "certification_evidence_synthesizes_maturity_extension": [
                    "certification_bundle_generates_maturity_extension_without_manual_flags",
                    "registry_projection_synthesizes_maturity_from_certification_extension",
                    "certification_evidence_synthesizer_bounds_mismatch_and_incomplete_claims",
                ],
                "registry_read_model_exposes_maturity": [
                    "read_model_projection_attaches_maturity_to_capabilities_and_records",
                ],
                "default_pack_C6_examples_projected": [
                    "capability_fabric_env_loader_installs_checked_in_default_packs",
                    "default_read_model_projects_governed_capability_records",
                ],
                "effect_bearing_production_requires_live_write": [
                    "effect_bearing_capability_requires_live_write_for_production",
                    "effect_bearing_c6_requires_live_write",
                ],
                "autonomy_requires_C7_controls": [
                    "autonomy_controls_assess_to_c7_when_production_ready",
                    "autonomy_controls_do_not_override_production_blockers",
                    "autonomy_requires_c7",
                ],
            },
        ),
        _surface(
            "capability_manifest_registry",
            [
                "CapabilityManifestRegistry.admit_path",
                "CapabilityManifestRegistry.admit_directory",
                "build_software_dev_capability_manifest_registry",
                "MaturityProjectingCapabilityAdmissionGate.read_model",
                "CapabilityManifest",
                "CapabilityManifestAdmission",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "capabilities/software_dev/manifests/software_dev_app_task_graph_plan.capability.json",
                "capabilities/software_dev/manifests/software_dev_change_run.capability.json",
                "capabilities/software_dev/manifests/software_dev_context_bundle_build.capability.json",
                "capabilities/software_dev/manifests/software_dev_gate_plan_select.capability.json",
                "capabilities/software_dev/manifests/software_dev_pr_candidate_prepare.capability.json",
                "capabilities/software_dev/manifests/software_dev_repo_map_read.capability.json",
                "gateway/capability_fabric.py",
                "mcoi/mcoi_runtime/contracts/capability_manifest.py",
                "mcoi/mcoi_runtime/core/capability_manifest_registry.py",
                "schemas/software_dev/capability_manifest.schema.json",
                "tests/test_gateway/test_capability_fabric.py",
                "tests/test_software_dev_capability_manifest_registry.py",
            ],
            "Capability manifest registry admits dynamic capability declarations only after owner, policy, evidence, schema, receipt, maturity, sandbox, rollback, environment, and hot-reload constraints validate; gateway fabric projects admitted manifests only when explicitly enabled; production hot reload remains denied for effect-bearing capabilities.",
            [
                "capability_manifest_schema_valid",
                "software_dev_manifests_admit_locally",
                "manifest_missing_policy_rejected",
                "manifest_unresolved_schema_rejected",
                "effect_manifest_requires_sandbox_rollback",
                "hot_reload_metadata_enforced",
                "production_hot_reload_denied_for_effect_manifest",
                "fabric_projects_local_manifest_registry",
                "fabric_rejects_production_hot_reload_manifest_registry",
            ],
            runtime_witness_anchor_aliases={
                "capability_manifest_schema_valid": [
                    "software_dev_capability_manifests_are_schema_valid",
                ],
                "software_dev_manifests_admit_locally": [
                    "capability_manifest_registry_admits_software_dev_directory_locally",
                ],
                "manifest_missing_policy_rejected": [
                    "capability_manifest_registry_rejects_missing_policy_refs",
                ],
                "manifest_unresolved_schema_rejected": [
                    "capability_manifest_registry_rejects_unresolved_schema_refs",
                ],
                "effect_manifest_requires_sandbox_rollback": [
                    "capability_manifest_registry_blocks_effects_without_sandbox_and_rollback",
                ],
                "hot_reload_metadata_enforced": [
                    "capability_manifest_registry_enforces_hot_reload_metadata_environment",
                    "capability_manifest_registry_requires_hot_reload_metadata",
                ],
                "production_hot_reload_denied_for_effect_manifest": [
                    "capability_manifest_registry_blocks_production_hot_reload_for_effects",
                ],
                "fabric_projects_local_manifest_registry": [
                    "capability_fabric_env_loader_projects_local_manifest_registry",
                ],
                "fabric_rejects_production_hot_reload_manifest_registry": [
                    "capability_fabric_env_loader_rejects_production_hot_reload_for_manifest_registry",
                ],
            },
        ),
        _surface(
            "networked_worker_mesh",
            [
                "NetworkedWorkerMesh.register_worker",
                "NetworkedWorkerMesh.dispatch",
                "NetworkedWorkerMesh.read_model",
                "SandboxedCodeWorker.execute_command",
                "CodeWorkerLease",
                "CodeWorkerReceipt",
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
                "mcoi/mcoi_runtime/contracts/code_worker.py",
                "mcoi/mcoi_runtime/workers/code_worker.py",
                "scripts/produce_physical_worker_canary.py",
                "schemas/physical_action_receipt.schema.json",
                "schemas/worker_mesh.schema.json",
                "tests/test_code_worker.py",
                "tests/test_gateway/test_physical_action_boundary.py",
                "tests/test_gateway/test_physical_worker_canary.py",
                "tests/test_gateway/test_worker_mesh.py",
                "tests/test_produce_physical_worker_canary.py",
            ],
            "Networked worker mesh dispatches only through active leases, rejects tenant/capability/operation/budget violations before handler execution, requires admitted physical action receipts for physical workers, and emits schema-backed receipts that explicitly require terminal closure; the sandboxed code worker adds exact-command leases, no-network sandbox dispatch, denied shell/network/git controls, and command/output hash receipts.",
            [
                "active_lease_required",
                "tenant_capability_operation_budget_checked",
                "forbidden_operations_override_allowed",
                "code_worker_exact_lease_command_required",
                "code_worker_blocks_network_shell_and_risky_git",
                "code_worker_receipt_binds_sandbox_evidence",
                "physical_action_receipt_required_for_physical_workers",
                "physical_worker_canary_blocks_without_receipt",
                "physical_worker_canary_passed",
                "physical_worker_canary_uses_sandbox_handler",
                "worker_evidence_refs_required",
                "worker_receipt_not_terminal_closure",
                "worker_mesh_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "active_lease_required": ["worker_mesh_rejects_invalid_or_expired_leases"],
                "tenant_capability_operation_budget_checked": [
                    "worker_mesh_rejects_tenant_and_capability_mismatch",
                    "worker_mesh_enforces_operation_and_cost_budgets",
                ],
                "forbidden_operations_override_allowed": [
                    "worker_mesh_rejects_forbidden_operation_before_handler"
                ],
                "code_worker_exact_lease_command_required": [
                    "sandboxed_code_worker_executes_exact_lease_command_with_receipt"
                ],
                "code_worker_blocks_network_shell_and_risky_git": [
                    "sandboxed_code_worker_blocks_network_and_risky_git_without_dispatch"
                ],
                "code_worker_receipt_binds_sandbox_evidence": [
                    "sandboxed_code_worker_executes_exact_lease_command_with_receipt"
                ],
                "physical_action_receipt_required_for_physical_workers": [
                    "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay"
                ],
                "physical_worker_canary_blocks_without_receipt": [
                    "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay"
                ],
                "physical_worker_canary_passed": [
                    "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay"
                ],
                "physical_worker_canary_uses_sandbox_handler": [
                    "physical_worker_canary_artifact_preserves_no_effect_proof"
                ],
                "worker_evidence_refs_required": [
                    "worker_mesh_requires_evidence_for_successful_handler"
                ],
                "worker_receipt_not_terminal_closure": [
                    "worker_mesh_dispatch_emits_schema_valid_non_terminal_receipt"
                ],
                "worker_mesh_schema_valid": [
                    "worker_mesh_dispatch_emits_schema_valid_non_terminal_receipt"
                ],
            },
        ),
        _surface(
            "software_dev_capability_pack",
            [
                "load_software_dev_domain_capsule",
                "load_software_dev_capability_entries",
                "build_software_dev_capability_admission_gate",
                "software_dev.repo_map.read",
                "software_dev.context_bundle.build",
                "software_dev.gate_plan.select",
                "software_dev.change.run",
                "software_dev.app_task_graph.plan",
                "software_dev.pr_candidate.prepare",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "capsules/software_dev.json",
                "capabilities/software_dev/capability_pack.json",
                "gateway/capability_fabric.py",
                "mcoi/mcoi_runtime/contracts/app_builder.py",
                "mcoi/mcoi_runtime/contracts/code_context.py",
                "mcoi/mcoi_runtime/contracts/code_intelligence.py",
                "mcoi/mcoi_runtime/contracts/code_worker.py",
                "mcoi/mcoi_runtime/contracts/pr_candidate.py",
                "mcoi/mcoi_runtime/core/app_builder/codegen_pipeline.py",
                "mcoi/mcoi_runtime/core/app_builder/pr_candidate.py",
                "mcoi/mcoi_runtime/core/code_context_builder.py",
                "mcoi/mcoi_runtime/core/code_intelligence.py",
                "mcoi/mcoi_runtime/core/software_gate_planner.py",
                "mcoi/mcoi_runtime/workers/code_worker.py",
                "schemas/software_dev/app_task_graph.input.schema.json",
                "schemas/software_dev/app_task_graph.output.schema.json",
                "schemas/software_dev/change_run.input.schema.json",
                "schemas/software_dev/code_context_bundle.output.schema.json",
                "schemas/software_dev/context_bundle.input.schema.json",
                "schemas/software_dev/gate_plan.input.schema.json",
                "schemas/software_dev/pr_candidate.output.schema.json",
                "schemas/software_dev/pr_candidate.input.schema.json",
                "schemas/software_dev/repo_map.output.schema.json",
                "schemas/software_dev/repo_map_read.input.schema.json",
                "schemas/software_dev/software_change_receipt.output.schema.json",
                "schemas/software_dev/software_gate_plan.output.schema.json",
                "tests/test_app_builder_pipeline.py",
                "tests/test_code_context_builder.py",
                "tests/test_code_intelligence.py",
                "tests/test_code_worker.py",
                "tests/test_pr_candidate.py",
                "tests/test_software_dev_capability_pack.py",
                "tests/test_software_gate_planner.py",
            ],
            "Software-development capability pack keeps repo intelligence, context building, gate planning, governed change execution, app task graph planning, and PR candidate preparation behind explicit capsule admission; default packs do not load it, read-only capabilities expose no execution authority, effectful capabilities require sandboxing, approval, receipts, recovery evidence, and direct-deployment denial, and PR candidate commands remain local git-only with push disabled.",
            [
                "software_dev_pack_fixture_not_default_loaded",
                "software_dev_capability_entries_schema_valid",
                "software_dev_input_schema_refs_materialized",
                "software_dev_input_schemas_reject_boundary_violations",
                "software_dev_output_schema_refs_materialized",
                "software_dev_output_schemas_reject_effect_overclaims",
                "software_dev_named_loader_installs_only_software_dev_domain",
                "software_dev_capsule_refs_match_pack_capabilities",
                "software_dev_pack_explicit_fabric_admits_known_capabilities",
                "software_dev_gate_projects_manifest_registry",
                "software_dev_direct_deployment_capability_absent",
                "software_dev_read_only_records_non_mutating",
                "software_dev_effectful_records_require_sandbox_approval",
                "software_dev_pr_candidate_blocks_git_push",
                "software_dev_pr_candidate_local_commands_are_git_local_only",
                "software_dev_production_ready_overclaim_rejected",
            ],
            runtime_witness_anchor_aliases={
                "software_dev_pack_fixture_not_default_loaded": [
                    "software_dev_fixture_pack_is_not_loaded_by_default"
                ],
                "software_dev_capability_entries_schema_valid": [
                    "software_dev_capability_entries_are_schema_valid"
                ],
                "software_dev_input_schema_refs_materialized": [
                    "software_dev_input_schema_refs_are_materialized_and_strict"
                ],
                "software_dev_output_schema_refs_materialized": [
                    "software_dev_output_schema_refs_are_materialized_and_strict"
                ],
                "software_dev_capsule_refs_match_pack_capabilities": [
                    "software_dev_capsule_references_exact_pack_capabilities"
                ],
                "software_dev_pack_explicit_fabric_admits_known_capabilities": [
                    "software_dev_pack_installs_through_explicit_capability_fabric"
                ],
                "software_dev_gate_projects_manifest_registry": [
                    "software_dev_named_loader_projects_manifest_registry_when_configured"
                ],
                "software_dev_direct_deployment_capability_absent": [
                    "software_dev_capsule_references_exact_pack_capabilities"
                ],
                "software_dev_read_only_records_non_mutating": [
                    "software_dev_governed_records_bind_read_and_effect_boundaries"
                ],
                "software_dev_effectful_records_require_sandbox_approval": [
                    "software_dev_governed_records_bind_read_and_effect_boundaries"
                ],
                "software_dev_pr_candidate_blocks_git_push": [
                    "local_git_command_contract_rejects_push_and_invalid_refs"
                ],
                "software_dev_production_ready_overclaim_rejected": [
                    "software_dev_pack_blocks_production_ready_overclaim"
                ],
            },
        ),
        _surface(
            "agentic_control_capability_pack",
            [
                "agentic_control.mission.define",
                "agentic_control.priority.rank",
                "agentic_control.governance_gate.evaluate",
                "agentic_control.resource_budget.bound",
                "agentic_control.math_algorithm.analyze",
                "agentic_control.security_threat_model.build",
                "agentic_control.swarm.coordinate",
                "agentic_control.product_management.plan",
                "agentic_control.verification.plan",
                "agentic_control.interrogation.plan",
                "agentic_control.self_audit.refine",
                "agentic_control.memory_admission.plan",
                "agentic_control.incident_recovery.plan",
                "agentic_control.telemetry_triage.plan",
                "agentic_control.code_change.plan",
                "agentic_control.release_handoff.plan",
                "agentic_control.evidence.append",
                "agentic_control.project_discipline_mesh.v1",
                "agentic_control.goal_governor.v1",
                "agentic_control.strategy_governor.v1",
                "agentic_control.decision_governor.v1",
                "agentic_control.design_governor.v1",
                "agentic_control.product_governor.v1",
                "agentic_control.management_governor.v1",
                "agentic_control.resource_governor.v1",
                "agentic_control.policy_governor.v1",
                "agentic_control.approval_governor.v1",
                "agentic_control.temporal_governor.v1",
                "agentic_control.memory_governor.v1",
                "agentic_control.evidence_governor.v1",
                "agentic_control.math_governor.v1",
                "agentic_control.algorithm_governor.v1",
                "agentic_control.security_governor.v1",
                "agentic_control.swarm_governor.v1",
                "agentic_control.coding_governor.v1",
                "agentic_control.quality_governor.v1",
                "agentic_control.execution_governor.v1",
                "agentic_control.runtime_governor.v1",
                "agentic_control.release_governor.v1",
                "agentic_control.autonomous_operations.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "capsules/agentic_control.json",
                "capabilities/agentic_control/capability_pack.json",
                "gateway/capability_fabric.py",
                "mcoi/mcoi_runtime/core/default_skill_catalog.py",
                "schemas/agentic_control/control_action.input.schema.json",
                "schemas/agentic_control/control_action.output.schema.json",
                "tests/test_gateway/test_agentic_control_capability_pack.py",
                "tests/test_gateway/test_capability_fabric.py",
                "mcoi/tests/test_default_skill_catalog.py",
            ],
            "Agentic-control capability pack admits bounded autonomous mission control, prioritization, governance gating, resource bounding, algorithm review, threat modeling, swarm coordination, product planning, verification planning, interrogation, recursive refinement, memory-admission planning, incident-recovery planning, telemetry-triage planning, code-change planning, release-handoff planning, evidence ledger append, Project Discipline Mesh scanning, goal-governor planning, strategy-governor planning, decision-governor planning, design-governor planning, product-governor planning, management-governor planning, resource-governor planning, policy-governor planning, approval-governor planning, temporal-governor planning, memory-governor planning, evidence-governor planning, math-governor planning, algorithm-governor planning, security-governor planning, swarm-governor planning, coding-governor planning, quality-governor planning, execution-governor planning, runtime-governor planning, release-governor planning, and autonomous operations behind governed default-pack admission; the evidence append path is world-mutating, approval-gated, receipt-bound, and blocked from production readiness without live evidence.",
            [
                "agentic_control_capability_entries_schema_valid",
                "agentic_control_pack_projects_governed_authority_records",
                "agentic_control_schemas_accept_representative_contracts",
                "agentic_control_schemas_reject_unbounded_or_unknown_payloads",
                "agentic_control_production_gate_blocks_without_live_evidence",
            ],
            runtime_witness_anchor_aliases={
                "agentic_control_capability_entries_schema_valid": [
                    "agentic_control_capability_entries_are_schema_valid"
                ],
            },
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
            runtime_witness_anchor_aliases={
                "owner_tenant_identity_required": [
                    "agent_identity_registers_schema_valid_accountable_record"
                ],
                "self_approval_forbidden": [
                    "agent_identity_denies_self_approval_and_policy_mutation"
                ],
                "policy_mutation_forbidden": [
                    "agent_identity_denies_self_approval_and_policy_mutation"
                ],
                "delegation_requires_lease": [
                    "agent_identity_delegation_requires_lease_scope"
                ],
                "agent_budget_enforced": [
                    "agent_identity_enforces_memory_and_budget_scope"
                ],
                "reputation_update_requires_evidence": [
                    "agent_reputation_update_requires_evidence_and_stays_bounded"
                ],
                "agent_identity_schema_valid": [
                    "agent_identity_registers_schema_valid_accountable_record"
                ],
            },
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
            runtime_witness_anchor_aliases={
                "claim_type_declared": [
                    "claim_verification_report_schema_validates"
                ],
                "contradictions_block_execution": [
                    "contradicted_claim_blocks_planning_and_execution"
                ],
                "stale_claims_block_execution": [
                    "stale_claim_blocks_execution"
                ],
                "high_risk_requires_independent_support": [
                    "high_risk_claim_requires_independent_support_sources"
                ],
                "claim_verification_schema_valid": [
                    "claim_verification_report_schema_validates"
                ],
            },
        ),
        _surface(
            "governed_connector_framework",
            [
                "/api/v1/connectors",
                "/api/v1/connectors/history",
                "/api/v1/connectors/invoke",
                "/api/v1/connectors/register",
                "/api/v1/connectors/summary",
                "/api/v1/connectors/{connector_id}/disable",
                "/api/v1/connectors/{connector_id}/enable",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/connectors.py",
                "mcoi/mcoi_runtime/core/connector_framework.py",
                "mcoi/tests/test_connector_framework.py",
                "mcoi/tests/test_server_phase217.py",
                "mcoi/tests/test_server_phase218.py",
                "docs/64_durable_gmail_connector_runtime_plan.md",
                "schemas/durable_gmail_oauth_operator_handoff.schema.json",
                "scripts/produce_durable_gmail_oauth_operator_handoff.py",
                "scripts/validate_durable_gmail_oauth_operator_handoff.py",
                "tests/test_produce_durable_gmail_oauth_operator_handoff.py",
                "tests/test_validate_durable_gmail_oauth_operator_handoff.py",
                "schemas/team_ops_shared_inbox_operator_handoff.schema.json",
                "scripts/produce_team_ops_shared_inbox_operator_handoff.py",
                "scripts/validate_team_ops_shared_inbox_operator_handoff.py",
                "tests/test_produce_team_ops_shared_inbox_operator_handoff.py",
                "tests/test_validate_team_ops_shared_inbox_operator_handoff.py",
                "schemas/team_ops_shared_inbox_live_probe_approval_binding.schema.json",
                "scripts/bind_team_ops_shared_inbox_live_probe_approval.py",
                "scripts/validate_team_ops_shared_inbox_live_probe_approval_binding.py",
                "tests/test_bind_team_ops_shared_inbox_live_probe_approval.py",
                "tests/test_validate_team_ops_shared_inbox_live_probe_approval_binding.py",
                "schemas/team_ops_shared_inbox_live_probe_authority.schema.json",
                "scripts/produce_team_ops_shared_inbox_live_probe_authority.py",
                "scripts/validate_team_ops_shared_inbox_live_probe_authority.py",
                "tests/test_produce_team_ops_shared_inbox_live_probe_authority.py",
                "tests/test_validate_team_ops_shared_inbox_live_probe_authority.py",
                "schemas/team_ops_shared_inbox_live_probe_operator_input_request.schema.json",
                "scripts/emit_team_ops_shared_inbox_live_probe_operator_input_request.py",
                "scripts/validate_team_ops_shared_inbox_live_probe_operator_input_request.py",
                "tests/test_emit_team_ops_shared_inbox_live_probe_operator_input_request.py",
                "tests/test_validate_team_ops_shared_inbox_live_probe_operator_input_request.py",
                "schemas/team_ops_shared_inbox_live_probe_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_live_probe_receipt.py",
                "scripts/validate_team_ops_shared_inbox_live_probe_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_live_probe_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_live_probe_receipt.py",
                "schemas/team_ops_shared_inbox_observation_routing_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_observation_routing_receipt.py",
                "scripts/validate_team_ops_shared_inbox_observation_routing_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_observation_routing_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_observation_routing_receipt.py",
                "schemas/team_ops_shared_inbox_approval_queue_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_approval_queue_receipt.py",
                "scripts/validate_team_ops_shared_inbox_approval_queue_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_approval_queue_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_approval_queue_receipt.py",
                "schemas/team_ops_shared_inbox_approval_decision_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_approval_decision_receipt.py",
                "scripts/validate_team_ops_shared_inbox_approval_decision_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_approval_decision_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_approval_decision_receipt.py",
                "schemas/team_ops_shared_inbox_send_preparation_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_send_preparation_receipt.py",
                "scripts/validate_team_ops_shared_inbox_send_preparation_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_send_preparation_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_send_preparation_receipt.py",
                "schemas/team_ops_shared_inbox_send_execution_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_send_execution_receipt.py",
                "scripts/validate_team_ops_shared_inbox_send_execution_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_send_execution_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_send_execution_receipt.py",
                "schemas/team_ops_shared_inbox_sent_message_observation_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_sent_message_observation_receipt.py",
                "scripts/validate_team_ops_shared_inbox_sent_message_observation_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_sent_message_observation_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_sent_message_observation_receipt.py",
                "schemas/team_ops_shared_inbox_terminal_closure_review_packet.schema.json",
                "scripts/produce_team_ops_shared_inbox_terminal_closure_review_packet.py",
                "scripts/validate_team_ops_shared_inbox_terminal_closure_review_packet.py",
                "tests/test_produce_team_ops_shared_inbox_terminal_closure_review_packet.py",
                "tests/test_validate_team_ops_shared_inbox_terminal_closure_review_packet.py",
                "scripts/mint_team_ops_shared_inbox_terminal_closure_certificate.py",
                "scripts/validate_team_ops_shared_inbox_terminal_closure_certificate.py",
                "tests/test_mint_team_ops_shared_inbox_terminal_closure_certificate.py",
                "tests/test_validate_team_ops_shared_inbox_terminal_closure_certificate.py",
                "scripts/produce_team_ops_shared_inbox_terminal_closure_evidence_bundle.py",
                "scripts/validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.py",
                "tests/test_produce_team_ops_shared_inbox_terminal_closure_evidence_bundle.py",
                "tests/test_validate_team_ops_shared_inbox_terminal_closure_evidence_bundle.py",
                "schemas/team_ops_shared_inbox_terminal_closure_anchor_preflight.schema.json",
                "scripts/produce_team_ops_shared_inbox_terminal_closure_anchor_preflight.py",
                "scripts/validate_team_ops_shared_inbox_terminal_closure_anchor_preflight.py",
                "tests/test_produce_team_ops_shared_inbox_terminal_closure_anchor_preflight.py",
                "tests/test_validate_team_ops_shared_inbox_terminal_closure_anchor_preflight.py",
                "schemas/team_ops_shared_inbox_terminal_closure_anchor_receipt.schema.json",
                "scripts/produce_team_ops_shared_inbox_terminal_closure_anchor_receipt.py",
                "scripts/validate_team_ops_shared_inbox_terminal_closure_anchor_receipt.py",
                "tests/test_produce_team_ops_shared_inbox_terminal_closure_anchor_receipt.py",
                "tests/test_validate_team_ops_shared_inbox_terminal_closure_anchor_receipt.py",
            ],
            "Governed connector routes register typed connector definitions, invoke handlers through guard-chain admission, bound lifecycle enable/disable controls, expose bounded list/history/summary read models, sanitize connector errors before returning operator-visible receipts, bind durable Gmail OAuth handoff evidence to schema-backed operator authority before live probe promotion, and gate TeamOps shared inbox read-only probe approval binding, authority, operator-input readiness, observation receipt binding, no-send observation routing, approval queue obligations, approval decision evidence, send-preparation evidence, send-execution evidence, sent-message observation/replay closure evidence, terminal closure review packets, TeamOps terminal closure certificates, signed TeamOps terminal closure evidence bundles, no-effect terminal anchor preflights, and pending local terminal anchor receipt wrappers behind handoff readiness, separate approval evidence, redacted read-only evidence, approval-before-send obligations, provider-send evidence refs, duplicate-absence observation, deterministic replay, certificate-minting separation, source-review binding, trust-ledger proof refs, HMAC verification, anchor artifact projection, operator authority, anchor-secret presence, ready-preflight binding, pending anchor receipt signatures, and no local provider-mutation or remote anchor-submission requirements.",
            [
                "connector_registration_typed",
                "connector_invocation_guard_chain_checked",
                "connector_lifecycle_disable_enable_bounded",
                "connector_history_summary_bounded",
                "connector_errors_sanitized",
                "connector_invocation_audited",
                "durable_gmail_oauth_handoff_blocks_until_authority",
                "durable_gmail_oauth_handoff_blocks_default_as_evidence",
                "durable_gmail_oauth_handoff_requires_live_probe_authority",
                "durable_gmail_oauth_handoff_redacts_secret_markers",
                "durable_gmail_oauth_handoff_accepts_ready_probe",
                "durable_gmail_oauth_handoff_writes_validation_receipt",
                "durable_gmail_oauth_uses_github_repo_inventory",
                "durable_gmail_oauth_blocks_case_insensitive_secret_markers",
                "durable_gmail_oauth_routes_witness_refs_as_variables",
                "durable_gmail_oauth_rejects_secret_markers_in_readable_signals",
                "durable_gmail_oauth_validates_repository_slug",
                "team_ops_shared_inbox_handoff_blocks_until_authority",
                "team_ops_shared_inbox_handoff_blocks_default_as_evidence",
                "team_ops_shared_inbox_handoff_requires_live_probe_authority",
                "team_ops_shared_inbox_handoff_redacts_secret_markers",
                "team_ops_shared_inbox_handoff_accepts_ready_probe",
                "team_ops_shared_inbox_handoff_blocks_external_message_drift",
                "team_ops_shared_inbox_handoff_writes_validation_receipt",
                "team_ops_shared_inbox_probe_approval_binding_lists_blockers",
                "team_ops_shared_inbox_probe_approval_binding_allows_ready_handoff",
                "team_ops_shared_inbox_probe_approval_binding_blocks_invalid_handoff",
                "team_ops_shared_inbox_probe_approval_binding_blocks_effect_drift",
                "team_ops_shared_inbox_probe_approval_binding_redacts_secret_markers",
                "team_ops_shared_inbox_probe_approval_binding_writes_validation_receipt",
                "team_ops_shared_inbox_probe_authority_blocks_missing_handoff",
                "team_ops_shared_inbox_probe_authority_requires_probe_approval",
                "team_ops_shared_inbox_probe_authority_admits_read_only_probe",
                "team_ops_shared_inbox_probe_authority_blocks_effect_drift",
                "team_ops_shared_inbox_probe_authority_redacts_secret_markers",
                "team_ops_shared_inbox_probe_authority_writes_validation_receipt",
                "team_ops_shared_inbox_probe_input_request_lists_blockers",
                "team_ops_shared_inbox_probe_input_request_names_approval_binding_blockers",
                "team_ops_shared_inbox_probe_input_request_allows_admitted_authority",
                "team_ops_shared_inbox_probe_input_request_blocks_invalid_authority",
                "team_ops_shared_inbox_probe_input_request_blocks_effect_drift",
                "team_ops_shared_inbox_probe_input_request_redacts_secret_markers",
                "team_ops_shared_inbox_probe_input_request_writes_validation_receipt",
                "team_ops_shared_inbox_probe_receipt_blocks_without_operator_input",
                "team_ops_shared_inbox_probe_receipt_requires_observation_evidence",
                "team_ops_shared_inbox_probe_receipt_accepts_read_only_observation",
                "team_ops_shared_inbox_probe_receipt_blocks_effect_drift",
                "team_ops_shared_inbox_probe_receipt_redacts_secret_markers",
                "team_ops_shared_inbox_probe_receipt_writes_validation_receipt",
                "team_ops_shared_inbox_observation_routing_blocks_without_live_probe",
                "team_ops_shared_inbox_observation_routing_requires_redacted_observation",
                "team_ops_shared_inbox_observation_routing_accepts_assignment_plan",
                "team_ops_shared_inbox_observation_routing_blocks_effect_drift",
                "team_ops_shared_inbox_observation_routing_redacts_secret_markers",
                "team_ops_shared_inbox_observation_routing_writes_validation_receipt",
                "team_ops_shared_inbox_approval_queue_blocks_without_routing",
                "team_ops_shared_inbox_approval_queue_requires_request_evidence",
                "team_ops_shared_inbox_approval_queue_accepts_pending_obligation",
                "team_ops_shared_inbox_approval_queue_blocks_effect_drift",
                "team_ops_shared_inbox_approval_queue_redacts_secret_markers",
                "team_ops_shared_inbox_approval_queue_writes_validation_receipt",
                "team_ops_shared_inbox_approval_decision_blocks_without_queue",
                "team_ops_shared_inbox_approval_decision_requires_decision_evidence",
                "team_ops_shared_inbox_approval_decision_accepts_operator_decisions",
                "team_ops_shared_inbox_approval_decision_blocks_role_or_authorization_drift",
                "team_ops_shared_inbox_approval_decision_redacts_secret_markers",
                "team_ops_shared_inbox_approval_decision_writes_validation_receipt",
                "team_ops_shared_inbox_send_preparation_blocks_without_decision",
                "team_ops_shared_inbox_send_preparation_requires_preparation_evidence",
                "team_ops_shared_inbox_send_preparation_accepts_approved_packet",
                "team_ops_shared_inbox_send_preparation_blocks_denied_or_drift",
                "team_ops_shared_inbox_send_preparation_redacts_secret_markers",
                "team_ops_shared_inbox_send_preparation_writes_validation_receipt",
                "team_ops_shared_inbox_send_execution_blocks_without_preparation",
                "team_ops_shared_inbox_send_execution_requires_execution_evidence",
                "team_ops_shared_inbox_send_execution_accepts_provider_receipt",
                "team_ops_shared_inbox_send_execution_blocks_drift_or_local_provider_claim",
                "team_ops_shared_inbox_send_execution_redacts_secret_markers",
                "team_ops_shared_inbox_send_execution_writes_validation_receipt",
                "team_ops_shared_inbox_sent_message_observation_blocks_without_execution",
                "team_ops_shared_inbox_sent_message_observation_requires_observation_replay",
                "team_ops_shared_inbox_sent_message_observation_accepts_replay_closure",
                "team_ops_shared_inbox_sent_message_observation_blocks_inconsistent_or_local_provider_claim",
                "team_ops_shared_inbox_sent_message_observation_redacts_secret_markers",
                "team_ops_shared_inbox_sent_message_observation_writes_validation_receipt",
                "team_ops_shared_inbox_terminal_closure_review_blocks_without_observation",
                "team_ops_shared_inbox_terminal_closure_review_requires_ready_packet",
                "team_ops_shared_inbox_terminal_closure_review_accepts_candidate_packet",
                "team_ops_shared_inbox_terminal_closure_review_blocks_certificate_or_raw_claim",
                "team_ops_shared_inbox_terminal_closure_review_redacts_secret_markers",
                "team_ops_shared_inbox_terminal_closure_review_writes_validation_receipt",
                "team_ops_shared_inbox_terminal_closure_certificate_blocks_without_ready_review",
                "team_ops_shared_inbox_terminal_closure_certificate_mints_schema_valid_certificate",
                "team_ops_shared_inbox_terminal_closure_certificate_binds_source_review_packet",
                "team_ops_shared_inbox_terminal_closure_certificate_rejects_generic_or_drifted_certificate",
                "team_ops_shared_inbox_terminal_closure_certificate_blocks_raw_secret_or_production_claim",
                "team_ops_shared_inbox_terminal_closure_certificate_writes_certificate_and_validation_receipts",
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_blocks_missing_secret",
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_signs_ready_certificate",
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_verifies_hmac",
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_binds_source_certificate",
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_blocks_raw_secret_or_production_claim",
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_writes_bundle_and_validation_receipts",
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_accepts_ready_bundle",
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_missing_authority_or_secret",
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_projects_anchor_artifacts",
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_invalid_bundle_or_target",
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_effect_or_raw_claim",
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_writes_preflight_and_validation_receipts",
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_accepts_ready_preflight",
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_blocks_missing_or_unready_inputs",
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_binds_preflight_bundle_and_artifacts",
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_verifies_anchor_signature",
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_blocks_effect_or_raw_claim",
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_writes_receipt_and_validation_receipts",
            ],
            runtime_witness_anchor_aliases={
                "connector_registration_typed": [
                    "register_and_list",
                    "register_connector_endpoint",
                    "invalid_connector_type",
                ],
                "connector_invocation_guard_chain_checked": [
                    "invoke_success",
                    "invoke_connector_endpoint",
                    "invoke_guard_denied_is_bounded",
                    "connector_invoke_guard_denial_is_bounded",
                ],
                "connector_lifecycle_disable_enable_bounded": [
                    "disable_enable",
                    "connector_lifecycle_and_history_endpoints",
                ],
                "connector_history_summary_bounded": [
                    "history_bounded",
                    "summary",
                    "connectors_summary_endpoint",
                    "connector_lifecycle_and_history_endpoints",
                ],
                "connector_errors_sanitized": [
                    "invoke_handler_raises",
                    "invalid_connector_type_400",
                    "invalid_connector_type_is_bounded",
                    "connector_invoke_guard_denial_is_bounded",
                ],
                "connector_invocation_audited": [
                    "invoke_records_audit_trail",
                ],
                "durable_gmail_oauth_handoff_blocks_until_authority": [
                    "default_handoff_waits_for_operator_authority_and_redacts_values",
                    "durable_gmail_oauth_operator_handoff_accepts_blocked_packet",
                ],
                "durable_gmail_oauth_handoff_blocks_default_as_evidence": [
                    "durable_gmail_oauth_operator_handoff_rejects_default_as_evidence_drift",
                ],
                "durable_gmail_oauth_handoff_requires_live_probe_authority": [
                    "operator_approval_allows_provider_setup_not_live_probe",
                    "durable_gmail_oauth_operator_handoff_rejects_live_probe_drift",
                ],
                "durable_gmail_oauth_handoff_redacts_secret_markers": [
                    "handoff_rejects_secret_shaped_approval_ref",
                    "handoff_rejects_uppercase_secret_shaped_approval_ref",
                    "writer_and_cli_emit_redacted_blocked_packet",
                    "durable_gmail_oauth_operator_handoff_rejects_secret_marker",
                    "runtime_preflight_writer_rejects_uppercase_secret_marker",
                ],
                "durable_gmail_oauth_handoff_accepts_ready_probe": [
                    "presence_only_secret_inventory_admits_live_probe_with_approval",
                    "durable_gmail_oauth_operator_handoff_accepts_ready_packet",
                ],
                "durable_gmail_oauth_handoff_writes_validation_receipt": [
                    "durable_gmail_oauth_operator_handoff_cli_writes_validation",
                ],
                "durable_gmail_oauth_uses_github_repo_inventory": [
                    "github_repo_inventory_cli_uses_variables_and_secret_names",
                    "cli_uses_github_repo_inventory_for_live_probe_handoff",
                    "empty_local_overlay_does_not_mask_github_inventory",
                ],
                "durable_gmail_oauth_blocks_case_insensitive_secret_markers": [
                    "parse_github_variable_list_rejects_uppercase_secret_marker",
                    "runtime_preflight_detects_uppercase_secret_marker_leakage",
                    "runtime_preflight_writer_rejects_uppercase_secret_marker",
                    "handoff_rejects_uppercase_secret_shaped_approval_ref",
                ],
                "durable_gmail_oauth_routes_witness_refs_as_variables": [
                    "runtime_bindings_route_secrets_and_witness_refs_separately",
                    "durable_gmail_oauth_operator_handoff_rejects_binding_command_drift",
                ],
                "durable_gmail_oauth_rejects_secret_markers_in_readable_signals": [
                    "non_secret_runtime_signal_with_secret_marker_fails_closed",
                    "durable_gmail_oauth_operator_handoff_rejects_secret_marker",
                ],
                "durable_gmail_oauth_validates_repository_slug": [
                    "handoff_rejects_malformed_repository_slug",
                ],
                "team_ops_shared_inbox_handoff_blocks_until_authority": [
                    "team_ops_default_handoff_waits_for_operator_authority_and_redacts_values",
                    "team_ops_shared_inbox_operator_handoff_accepts_blocked_packet",
                ],
                "team_ops_shared_inbox_handoff_blocks_default_as_evidence": [
                    "team_ops_shared_inbox_operator_handoff_rejects_default_as_evidence_drift",
                ],
                "team_ops_shared_inbox_handoff_requires_live_probe_authority": [
                    "team_ops_operator_approval_allows_provider_setup_not_live_probe",
                    "team_ops_shared_inbox_operator_handoff_rejects_live_probe_drift",
                ],
                "team_ops_shared_inbox_handoff_redacts_secret_markers": [
                    "team_ops_handoff_rejects_secret_shaped_approval_ref",
                    "team_ops_writer_and_cli_emit_redacted_blocked_packet",
                    "team_ops_shared_inbox_operator_handoff_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_handoff_accepts_ready_probe": [
                    "team_ops_presence_only_secret_inventory_admits_live_probe_with_approval",
                    "team_ops_shared_inbox_operator_handoff_accepts_ready_packet",
                ],
                "team_ops_shared_inbox_handoff_blocks_external_message_drift": [
                    "team_ops_shared_inbox_operator_handoff_rejects_external_message_drift",
                ],
                "team_ops_shared_inbox_handoff_writes_validation_receipt": [
                    "team_ops_shared_inbox_operator_handoff_cli_writes_validation",
                ],
                "team_ops_shared_inbox_probe_approval_binding_lists_blockers": [
                    "missing_handoff_binding_blocks_without_external_effects",
                    "ready_handoff_without_probe_approval_blocks_binding",
                    "team_ops_live_probe_approval_binding_accepts_blocked_packet",
                ],
                "team_ops_shared_inbox_probe_approval_binding_allows_ready_handoff": [
                    "ready_handoff_with_probe_approval_binds_authority_input",
                    "team_ops_live_probe_approval_binding_accepts_ready_packet",
                    "ready_approval_binding_admits_authority_without_raw_ref",
                ],
                "team_ops_shared_inbox_probe_approval_binding_blocks_invalid_handoff": [
                    "team_ops_live_probe_approval_binding_rejects_ready_state_without_approval",
                ],
                "team_ops_shared_inbox_probe_approval_binding_blocks_effect_drift": [
                    "team_ops_live_probe_approval_binding_rejects_external_effect_drift",
                ],
                "team_ops_shared_inbox_probe_approval_binding_redacts_secret_markers": [
                    "approval_binding_rejects_secret_shaped_approval_ref",
                    "team_ops_live_probe_approval_binding_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_probe_approval_binding_writes_validation_receipt": [
                    "approval_binding_writer_and_cli_emit_blocked_receipt",
                    "team_ops_live_probe_approval_binding_cli_writes_validation",
                ],
                "team_ops_shared_inbox_probe_authority_blocks_missing_handoff": [
                    "missing_handoff_blocks_without_external_effects",
                    "team_ops_live_probe_authority_accepts_blocked_packet",
                ],
                "team_ops_shared_inbox_probe_authority_requires_probe_approval": [
                    "ready_handoff_without_probe_approval_blocks_authority",
                    "team_ops_live_probe_authority_rejects_admitted_state_without_approval",
                ],
                "team_ops_shared_inbox_probe_authority_admits_read_only_probe": [
                    "ready_handoff_with_probe_approval_admits_read_only_probe",
                    "team_ops_live_probe_authority_accepts_admitted_packet",
                ],
                "team_ops_shared_inbox_probe_authority_blocks_effect_drift": [
                    "team_ops_live_probe_authority_rejects_external_effect_drift",
                ],
                "team_ops_shared_inbox_probe_authority_redacts_secret_markers": [
                    "probe_authority_rejects_secret_shaped_approval_ref",
                    "team_ops_live_probe_authority_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_probe_authority_writes_validation_receipt": [
                    "probe_authority_writer_and_cli_emit_blocked_receipt",
                    "team_ops_live_probe_authority_cli_writes_validation",
                ],
                "team_ops_shared_inbox_probe_input_request_lists_blockers": [
                    "team_ops_live_probe_operator_input_request_reports_blocked_authority",
                    "team_ops_live_probe_operator_input_request_validation_accepts_blocked_request",
                ],
                "team_ops_shared_inbox_probe_input_request_names_approval_binding_blockers": [
                    "team_ops_live_probe_operator_input_request_reports_missing_approval_binding",
                    "team_ops_live_probe_operator_input_request_reports_invalid_approval_binding",
                    "team_ops_live_probe_operator_input_request_reports_not_ready_approval_binding",
                ],
                "team_ops_shared_inbox_probe_input_request_allows_admitted_authority": [
                    "team_ops_live_probe_operator_input_request_allows_admitted_authority",
                ],
                "team_ops_shared_inbox_probe_input_request_blocks_invalid_authority": [
                    "team_ops_live_probe_operator_input_request_blocks_invalid_authority",
                    "team_ops_live_probe_operator_input_request_validation_rejects_ready_drift",
                ],
                "team_ops_shared_inbox_probe_input_request_blocks_effect_drift": [
                    "team_ops_live_probe_operator_input_request_validation_rejects_effect_drift",
                ],
                "team_ops_shared_inbox_probe_input_request_redacts_secret_markers": [
                    "team_ops_live_probe_operator_input_request_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_probe_input_request_writes_validation_receipt": [
                    "team_ops_live_probe_operator_input_request_cli_writes_report",
                    "team_ops_live_probe_operator_input_request_validation_cli_writes_receipt",
                ],
                "team_ops_shared_inbox_probe_receipt_blocks_without_operator_input": [
                    "team_ops_shared_inbox_live_probe_receipt_blocks_without_operator_input_ready",
                    "team_ops_shared_inbox_live_probe_receipt_validation_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_probe_receipt_requires_observation_evidence": [
                    "team_ops_shared_inbox_live_probe_receipt_requires_observation_evidence",
                    "team_ops_shared_inbox_live_probe_receipt_validation_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_probe_receipt_accepts_read_only_observation": [
                    "team_ops_shared_inbox_live_probe_receipt_accepts_read_only_observation",
                    "team_ops_shared_inbox_live_probe_receipt_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_probe_receipt_blocks_effect_drift": [
                    "team_ops_shared_inbox_live_probe_receipt_blocks_count_over_authority",
                    "team_ops_shared_inbox_live_probe_receipt_validation_rejects_effect_drift",
                    "team_ops_shared_inbox_live_probe_receipt_validation_rejects_count_over_authority",
                    "team_ops_shared_inbox_live_probe_receipt_validation_rejects_raw_query_field",
                ],
                "team_ops_shared_inbox_probe_receipt_redacts_secret_markers": [
                    "team_ops_shared_inbox_live_probe_receipt_rejects_secret_marker_ref",
                    "team_ops_shared_inbox_live_probe_receipt_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_probe_receipt_writes_validation_receipt": [
                    "team_ops_shared_inbox_live_probe_receipt_cli_writes_report",
                    "team_ops_shared_inbox_live_probe_receipt_validation_cli_writes_receipt",
                ],
                "team_ops_shared_inbox_observation_routing_blocks_without_live_probe": [
                    "team_ops_shared_inbox_observation_routing_blocks_without_live_probe_ready",
                    "team_ops_shared_inbox_observation_routing_validation_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_observation_routing_requires_redacted_observation": [
                    "team_ops_shared_inbox_observation_routing_requires_redacted_observation",
                    "team_ops_shared_inbox_observation_routing_validation_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_observation_routing_accepts_assignment_plan": [
                    "team_ops_shared_inbox_observation_routing_accepts_assignment_plan",
                    "team_ops_shared_inbox_observation_routing_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_observation_routing_blocks_effect_drift": [
                    "team_ops_shared_inbox_observation_routing_blocks_unknown_classification",
                    "team_ops_shared_inbox_observation_routing_validation_rejects_effect_drift",
                    "team_ops_shared_inbox_observation_routing_validation_rejects_raw_fields",
                    "team_ops_shared_inbox_observation_routing_validation_rejects_unknown_classification",
                    "team_ops_shared_inbox_observation_routing_validation_rejects_missing_owner",
                ],
                "team_ops_shared_inbox_observation_routing_redacts_secret_markers": [
                    "team_ops_shared_inbox_observation_routing_rejects_secret_marker_ref",
                    "team_ops_shared_inbox_observation_routing_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_observation_routing_writes_validation_receipt": [
                    "team_ops_shared_inbox_observation_routing_cli_writes_report",
                    "team_ops_shared_inbox_observation_routing_validation_cli_writes_receipt",
                    "team_ops_shared_inbox_observation_routing_validation_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_approval_queue_blocks_without_routing": [
                    "team_ops_shared_inbox_approval_queue_blocks_without_routing_ready",
                    "team_ops_shared_inbox_approval_queue_validation_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_approval_queue_requires_request_evidence": [
                    "team_ops_shared_inbox_approval_queue_requires_request_evidence",
                    "team_ops_shared_inbox_approval_queue_validation_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_approval_queue_accepts_pending_obligation": [
                    "team_ops_shared_inbox_approval_queue_accepts_pending_obligation",
                    "team_ops_shared_inbox_approval_queue_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_approval_queue_blocks_effect_drift": [
                    "team_ops_shared_inbox_approval_queue_validation_rejects_effect_drift",
                    "team_ops_shared_inbox_approval_queue_validation_rejects_raw_fields",
                    "team_ops_shared_inbox_approval_queue_validation_rejects_missing_request",
                    "team_ops_shared_inbox_approval_queue_validation_rejects_approval_decision_claim",
                ],
                "team_ops_shared_inbox_approval_queue_redacts_secret_markers": [
                    "team_ops_shared_inbox_approval_queue_rejects_secret_marker_ref",
                    "team_ops_shared_inbox_approval_queue_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_approval_queue_writes_validation_receipt": [
                    "team_ops_shared_inbox_approval_queue_cli_writes_report",
                    "team_ops_shared_inbox_approval_queue_validation_cli_writes_receipt",
                    "team_ops_shared_inbox_approval_queue_validation_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_approval_decision_blocks_without_queue": [
                    "team_ops_shared_inbox_approval_decision_blocks_without_queue_ready",
                    "team_ops_shared_inbox_approval_decision_validation_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_approval_decision_requires_decision_evidence": [
                    "team_ops_shared_inbox_approval_decision_requires_decision_evidence",
                    "team_ops_shared_inbox_approval_decision_validation_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_approval_decision_accepts_operator_decisions": [
                    "team_ops_shared_inbox_approval_decision_accepts_approved_decision",
                    "team_ops_shared_inbox_approval_decision_accepts_denied_no_send",
                    "team_ops_shared_inbox_approval_decision_validation_accepts_approved_receipt",
                    "team_ops_shared_inbox_approval_decision_validation_accepts_denied_receipt",
                ],
                "team_ops_shared_inbox_approval_decision_blocks_role_or_authorization_drift": [
                    "team_ops_shared_inbox_approval_decision_blocks_role_mismatch",
                    "team_ops_shared_inbox_approval_decision_validation_rejects_effect_drift",
                    "team_ops_shared_inbox_approval_decision_validation_rejects_raw_fields",
                    "team_ops_shared_inbox_approval_decision_validation_rejects_missing_evidence",
                    "team_ops_shared_inbox_approval_decision_validation_rejects_role_mismatch",
                    "team_ops_shared_inbox_approval_decision_validation_rejects_bad_authorization",
                ],
                "team_ops_shared_inbox_approval_decision_redacts_secret_markers": [
                    "team_ops_shared_inbox_approval_decision_rejects_secret_marker_ref",
                    "team_ops_shared_inbox_approval_decision_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_approval_decision_writes_validation_receipt": [
                    "team_ops_shared_inbox_approval_decision_cli_writes_report",
                    "team_ops_shared_inbox_approval_decision_validation_cli_writes_receipt",
                    "team_ops_shared_inbox_approval_decision_validation_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_send_preparation_blocks_without_decision": [
                    "team_ops_shared_inbox_send_preparation_blocks_without_decision_ready",
                    "team_ops_shared_inbox_send_preparation_validation_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_send_preparation_requires_preparation_evidence": [
                    "team_ops_shared_inbox_send_preparation_requires_preparation_evidence",
                    "team_ops_shared_inbox_send_preparation_validation_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_send_preparation_accepts_approved_packet": [
                    "team_ops_shared_inbox_send_preparation_accepts_approved_packet",
                    "team_ops_shared_inbox_send_preparation_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_send_preparation_blocks_denied_or_drift": [
                    "team_ops_shared_inbox_send_preparation_blocks_denied_decision",
                    "team_ops_shared_inbox_send_preparation_validation_rejects_denied_decision",
                    "team_ops_shared_inbox_send_preparation_validation_rejects_effect_drift",
                    "team_ops_shared_inbox_send_preparation_validation_rejects_raw_fields",
                    "team_ops_shared_inbox_send_preparation_validation_rejects_missing_preparation",
                    "team_ops_shared_inbox_send_preparation_validation_rejects_bad_hash",
                ],
                "team_ops_shared_inbox_send_preparation_redacts_secret_markers": [
                    "team_ops_shared_inbox_send_preparation_rejects_secret_marker_ref",
                    "team_ops_shared_inbox_send_preparation_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_send_preparation_writes_validation_receipt": [
                    "team_ops_shared_inbox_send_preparation_cli_writes_report",
                    "team_ops_shared_inbox_send_preparation_validation_cli_writes_receipt",
                    "team_ops_shared_inbox_send_preparation_validation_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_send_execution_blocks_without_preparation": [
                    "team_ops_shared_inbox_send_execution_blocks_without_preparation_ready",
                    "team_ops_shared_inbox_send_execution_validation_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_send_execution_requires_execution_evidence": [
                    "team_ops_shared_inbox_send_execution_requires_execution_evidence",
                    "team_ops_shared_inbox_send_execution_validation_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_send_execution_accepts_provider_receipt": [
                    "team_ops_shared_inbox_send_execution_accepts_provider_receipt",
                    "team_ops_shared_inbox_send_execution_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_send_execution_blocks_drift_or_local_provider_claim": [
                    "team_ops_shared_inbox_send_execution_blocks_preparation_drift",
                    "team_ops_shared_inbox_send_execution_validation_rejects_unready_preparation",
                    "team_ops_shared_inbox_send_execution_validation_rejects_local_provider_claim",
                    "team_ops_shared_inbox_send_execution_validation_rejects_raw_fields",
                    "team_ops_shared_inbox_send_execution_validation_rejects_missing_execution",
                    "team_ops_shared_inbox_send_execution_validation_rejects_bad_hash",
                ],
                "team_ops_shared_inbox_send_execution_redacts_secret_markers": [
                    "team_ops_shared_inbox_send_execution_rejects_secret_marker_ref",
                    "team_ops_shared_inbox_send_execution_validation_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_send_execution_writes_validation_receipt": [
                    "team_ops_shared_inbox_send_execution_cli_writes_report",
                    "team_ops_shared_inbox_send_execution_validation_cli_writes_receipt",
                    "team_ops_shared_inbox_send_execution_validation_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_sent_message_observation_blocks_without_execution": [
                    "team_ops_sent_message_observation_blocks_without_send_execution_ready",
                    "team_ops_sent_message_observation_validator_accepts_blocked_receipt",
                ],
                "team_ops_shared_inbox_sent_message_observation_requires_observation_replay": [
                    "team_ops_sent_message_observation_requires_observation_and_replay_evidence",
                    "team_ops_sent_message_observation_validator_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_sent_message_observation_accepts_replay_closure": [
                    "team_ops_sent_message_observation_accepts_two_observations_and_replay",
                    "team_ops_sent_message_observation_validator_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_sent_message_observation_blocks_inconsistent_or_local_provider_claim": [
                    "team_ops_sent_message_observation_blocks_hash_mismatch",
                    "team_ops_sent_message_observation_validator_rejects_local_provider_claim",
                    "team_ops_sent_message_observation_validator_rejects_raw_provider_field",
                    "team_ops_sent_message_observation_validator_rejects_missing_replay",
                    "team_ops_sent_message_observation_validator_rejects_bad_replay_hash",
                    "team_ops_sent_message_observation_validator_rejects_hash_mismatch",
                ],
                "team_ops_shared_inbox_sent_message_observation_redacts_secret_markers": [
                    "team_ops_sent_message_observation_rejects_secret_marker_ref",
                    "team_ops_sent_message_observation_validator_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_sent_message_observation_writes_validation_receipt": [
                    "team_ops_sent_message_observation_cli_writes_report",
                    "team_ops_sent_message_observation_validator_cli_writes_validation",
                    "team_ops_sent_message_observation_validator_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_terminal_closure_review_blocks_without_observation": [
                    "team_ops_terminal_closure_review_blocks_without_observation_ready",
                    "team_ops_terminal_closure_review_validator_accepts_blocked_packet",
                ],
                "team_ops_shared_inbox_terminal_closure_review_requires_ready_packet": [
                    "team_ops_terminal_closure_review_validator_require_ready_rejects_blocked",
                ],
                "team_ops_shared_inbox_terminal_closure_review_accepts_candidate_packet": [
                    "team_ops_terminal_closure_review_accepts_ready_observation",
                    "team_ops_terminal_closure_review_validator_accepts_ready_packet",
                ],
                "team_ops_shared_inbox_terminal_closure_review_blocks_certificate_or_raw_claim": [
                    "team_ops_terminal_closure_review_validator_rejects_certificate_mint_claim",
                    "team_ops_terminal_closure_review_validator_rejects_raw_provider_field",
                    "team_ops_terminal_closure_review_validator_rejects_bad_review_hash",
                ],
                "team_ops_shared_inbox_terminal_closure_review_redacts_secret_markers": [
                    "team_ops_terminal_closure_review_rejects_secret_marker_ref",
                    "team_ops_terminal_closure_review_validator_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_terminal_closure_review_writes_validation_receipt": [
                    "team_ops_terminal_closure_review_cli_writes_packet",
                    "team_ops_terminal_closure_review_validator_cli_writes_validation",
                    "team_ops_terminal_closure_review_validator_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_terminal_closure_certificate_blocks_without_ready_review": [
                    "team_ops_terminal_closure_certificate_blocks_unready_review",
                ],
                "team_ops_shared_inbox_terminal_closure_certificate_mints_schema_valid_certificate": [
                    "team_ops_terminal_closure_certificate_mints_ready_review",
                    "team_ops_terminal_closure_certificate_validator_accepts_ready_certificate",
                ],
                "team_ops_shared_inbox_terminal_closure_certificate_binds_source_review_packet": [
                    "team_ops_terminal_closure_certificate_validator_accepts_ready_certificate",
                    "team_ops_terminal_closure_certificate_validator_rejects_review_hash_drift",
                ],
                "team_ops_shared_inbox_terminal_closure_certificate_rejects_generic_or_drifted_certificate": [
                    "team_ops_terminal_closure_certificate_validator_rejects_generic_certificate",
                    "team_ops_terminal_closure_certificate_validator_rejects_review_hash_drift",
                ],
                "team_ops_shared_inbox_terminal_closure_certificate_blocks_raw_secret_or_production_claim": [
                    "team_ops_terminal_closure_certificate_rejects_secret_marker_review",
                    "team_ops_terminal_closure_certificate_validator_rejects_raw_field",
                    "team_ops_terminal_closure_certificate_validator_rejects_production_claim",
                    "team_ops_terminal_closure_certificate_validator_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_terminal_closure_certificate_writes_certificate_and_validation_receipts": [
                    "team_ops_terminal_closure_certificate_cli_writes_certificate",
                    "team_ops_terminal_closure_certificate_validator_cli_writes_validation",
                    "team_ops_terminal_closure_certificate_validator_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_blocks_missing_secret": [
                    "team_ops_terminal_closure_evidence_bundle_blocks_missing_secret",
                ],
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_signs_ready_certificate": [
                    "team_ops_terminal_closure_evidence_bundle_signs_ready_certificate",
                    "team_ops_terminal_closure_evidence_bundle_validator_accepts_ready_bundle",
                ],
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_verifies_hmac": [
                    "team_ops_terminal_closure_evidence_bundle_validator_accepts_ready_bundle",
                    "team_ops_terminal_closure_evidence_bundle_validator_rejects_wrong_secret",
                ],
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_binds_source_certificate": [
                    "team_ops_terminal_closure_evidence_bundle_signs_ready_certificate",
                    "team_ops_terminal_closure_evidence_bundle_validator_rejects_certificate_drift",
                ],
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_blocks_raw_secret_or_production_claim": [
                    "team_ops_terminal_closure_evidence_bundle_rejects_unready_certificate",
                    "team_ops_terminal_closure_evidence_bundle_validator_rejects_raw_field",
                    "team_ops_terminal_closure_evidence_bundle_validator_rejects_production_claim",
                    "team_ops_terminal_closure_evidence_bundle_validator_rejects_secret_marker",
                ],
                "team_ops_shared_inbox_terminal_closure_evidence_bundle_writes_bundle_and_validation_receipts": [
                    "team_ops_terminal_closure_evidence_bundle_cli_writes_bundle",
                    "team_ops_terminal_closure_evidence_bundle_validator_cli_writes_validation",
                    "team_ops_terminal_closure_evidence_bundle_validator_missing_path_is_bounded",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_accepts_ready_bundle": [
                    "team_ops_terminal_closure_anchor_preflight_accepts_ready_bundle",
                    "team_ops_terminal_closure_anchor_preflight_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_missing_authority_or_secret": [
                    "team_ops_terminal_closure_anchor_preflight_blocks_missing_anchor_secret",
                    "team_ops_terminal_closure_anchor_preflight_blocks_missing_authority",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_projects_anchor_artifacts": [
                    "team_ops_terminal_closure_anchor_preflight_accepts_ready_bundle",
                    "team_ops_terminal_closure_anchor_preflight_validation_rejects_artifact_drift",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_invalid_bundle_or_target": [
                    "team_ops_terminal_closure_anchor_preflight_blocks_invalid_target",
                    "team_ops_terminal_closure_anchor_preflight_validation_rejects_wrong_bundle_secret",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_blocks_effect_or_raw_claim": [
                    "team_ops_terminal_closure_anchor_preflight_validation_rejects_effect_claim",
                    "team_ops_terminal_closure_anchor_preflight_validation_rejects_raw_field",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_preflight_writes_preflight_and_validation_receipts": [
                    "team_ops_terminal_closure_anchor_preflight_cli_writes_blocked_receipt",
                    "team_ops_terminal_closure_anchor_preflight_validation_cli_writes_receipt",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_accepts_ready_preflight": [
                    "team_ops_terminal_closure_anchor_receipt_accepts_ready_preflight",
                    "team_ops_terminal_closure_anchor_receipt_validation_accepts_ready_receipt",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_blocks_missing_or_unready_inputs": [
                    "team_ops_terminal_closure_anchor_receipt_blocks_missing_anchor_secret",
                    "team_ops_terminal_closure_anchor_receipt_blocks_not_ready_preflight",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_binds_preflight_bundle_and_artifacts": [
                    "team_ops_terminal_closure_anchor_receipt_accepts_ready_preflight",
                    "team_ops_terminal_closure_anchor_receipt_validation_rejects_artifact_drift",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_verifies_anchor_signature": [
                    "team_ops_terminal_closure_anchor_receipt_validation_accepts_ready_receipt",
                    "team_ops_terminal_closure_anchor_receipt_validation_rejects_wrong_anchor_secret",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_blocks_effect_or_raw_claim": [
                    "team_ops_terminal_closure_anchor_receipt_validation_rejects_effect_claim",
                ],
                "team_ops_shared_inbox_terminal_closure_anchor_receipt_writes_receipt_and_validation_receipts": [
                    "team_ops_terminal_closure_anchor_receipt_cli_writes_ready_receipt",
                    "team_ops_terminal_closure_anchor_receipt_validation_cli_writes_receipt",
                ],
            },
        ),
        _surface(
            "governed_background_scheduler",
            [
                "/api/v1/scheduler/execute",
                "/api/v1/scheduler/history",
                "/api/v1/scheduler/jobs",
                "/api/v1/scheduler/jobs/{job_id}",
                "/api/v1/scheduler/jobs/{job_id}/disable",
                "/api/v1/scheduler/jobs/{job_id}/enable",
                "/api/v1/scheduler/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/scheduler.py",
                "mcoi/mcoi_runtime/core/scheduler.py",
                "mcoi/tests/test_scheduler.py",
                "mcoi/tests/test_server_phase217.py",
                "mcoi/tests/test_server_phase218.py",
            ],
            "Governed background scheduler routes register one-shot, interval, and cron jobs, execute handlers through guard-chain admission, bound job lifecycle enable/disable/delete controls, expose bounded history and summary read models, and sanitize scheduler execution errors.",
            [
                "scheduler_job_registration_typed",
                "scheduler_execute_guard_chain_checked",
                "scheduler_lifecycle_controls_bounded",
                "scheduler_history_summary_bounded",
                "scheduler_errors_sanitized",
                "scheduler_execution_audited",
            ],
            runtime_witness_anchor_aliases={
                "scheduler_job_registration_typed": [
                    "schedule_and_list_jobs",
                    "schedule_job_endpoint",
                    "invalid_schedule_type",
                ],
                "scheduler_execute_guard_chain_checked": [
                    "execute_job_succeeds",
                    "execute_job_guard_denied_is_bounded",
                    "scheduler_execute_guard_denial_is_bounded",
                    "scheduler_lifecycle_and_history_endpoints",
                ],
                "scheduler_lifecycle_controls_bounded": [
                    "disable_enable_job",
                    "unschedule_job",
                    "scheduler_lifecycle_and_history_endpoints",
                ],
                "scheduler_history_summary_bounded": [
                    "history_bounded",
                    "summary",
                    "scheduler_summary_endpoint",
                    "scheduler_lifecycle_and_history_endpoints",
                ],
                "scheduler_errors_sanitized": [
                    "execute_job_handler_not_found",
                    "execute_job_handler_raises",
                    "execute_nonexistent_job_error_is_bounded",
                    "invalid_schedule_type_400",
                    "invalid_schedule_type_is_bounded",
                    "scheduler_execute_missing_handler_is_bounded",
                    "scheduler_execute_guard_denial_is_bounded",
                ],
                "scheduler_execution_audited": [
                    "execute_job_records_audit_trail",
                ],
            },
        ),
        _surface(
            "multi_agent_coordination_runtime",
            [
                "/api/v1/multi-agent/conflict",
                "/api/v1/multi-agent/conflicts/unresolved",
                "/api/v1/multi-agent/delegate",
                "/api/v1/multi-agent/delegate/resolve",
                "/api/v1/multi-agent/handoff",
                "/api/v1/multi-agent/merge",
                "/api/v1/multi-agent/summary",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/multi_agent.py",
                "mcoi/mcoi_runtime/contracts/coordination.py",
                "mcoi/mcoi_runtime/core/coordination.py",
                "mcoi/tests/test_multi_agent_runtime.py",
                "mcoi/tests/test_server_phase217.py",
            ],
            "Multi-agent coordination routes bind delegation, resolution, handoff, merge, conflict recording, unresolved-conflict read models, and runtime summaries to the coordination engine with audit records and bounded error contracts.",
            [
                "multi_agent_delegation_tracked",
                "multi_agent_delegation_resolution_validated",
                "multi_agent_handoff_preserves_context",
                "multi_agent_merge_outcome_typed",
                "multi_agent_conflict_strategy_typed",
                "multi_agent_unresolved_conflicts_bounded",
                "multi_agent_summary_bounded",
                "multi_agent_errors_sanitized",
            ],
            runtime_witness_anchor_aliases={
                "multi_agent_delegation_tracked": [
                    "delegate_work",
                    "full_cooperation_flow",
                ],
                "multi_agent_delegation_resolution_validated": [
                    "resolve_delegation",
                    "invalid_delegation_status_detail_is_bounded",
                    "invalid_resolution_status_is_bounded",
                    "missing_delegation_resolution_has_bounded_failure_class",
                    "full_cooperation_flow",
                ],
                "multi_agent_handoff_preserves_context": [
                    "record_handoff",
                    "full_cooperation_flow",
                ],
                "multi_agent_merge_outcome_typed": [
                    "record_merge",
                    "invalid_merge_outcome_detail_is_bounded",
                    "invalid_merge_outcome_is_bounded",
                    "full_cooperation_flow",
                ],
                "multi_agent_conflict_strategy_typed": [
                    "record_conflict",
                    "invalid_conflict_strategy_detail_is_bounded",
                    "invalid_conflict_strategy_is_bounded",
                ],
                "multi_agent_unresolved_conflicts_bounded": [
                    "unresolved_conflicts",
                ],
                "multi_agent_summary_bounded": [
                    "multi_agent_summary",
                ],
                "multi_agent_errors_sanitized": [
                    "delegate_error_detail_is_bounded",
                    "invalid_delegation_status_detail_is_bounded",
                    "invalid_merge_outcome_detail_is_bounded",
                    "invalid_conflict_strategy_detail_is_bounded",
                    "missing_delegation_resolution_has_bounded_failure_class",
                ],
            },
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
            runtime_witness_anchor_aliases={
                "provider_success_not_assumed": [
                    "retryable_provider_failure_emits_retry_receipt_not_success"
                ],
                "write_failures_require_operator_review": [
                    "write_operation_failure_requires_operator_review"
                ],
                "missing_receipt_revokes_capability": [
                    "missing_receipt_revokes_capability_until_proof_restored"
                ],
                "fallback_provider_requires_certification": [
                    "fallback_provider_switch_requires_certification_and_fresh_receipt"
                ],
                "read_only_degradation_bounded": [
                    "read_only_degradation_is_bounded_for_non_write_failure"
                ],
                "connector_self_healing_schema_valid": [
                    "connector_self_healing_receipt_schema_validates"
                ],
            },
        ),
        _surface(
            "connector_action_promotion_gate",
            [
                "ConnectorActionPromotionGate",
                "validate_connector_action_promotion_gate",
                "connector_action_promotion_gate.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/connector_action_promotion_gate.schema.json",
                "examples/connector_action_promotion_gate.foundation.json",
                "scripts/validate_connector_action_promotion_gate.py",
                "tests/test_validate_connector_action_promotion_gate.py",
                "schemas/connector_descriptor.schema.json",
                "schemas/connector_result.schema.json",
                "schemas/universal_action_orchestration.schema.json",
                "docs/83_connector_action_promotion_gate_contract.md",
            ],
            "Connector action promotion gates bind connector descriptor/result evidence, UAO refs, Phi_gov authorization state, approval state, secret-access receipt state, connector-worker execution receipt state, rollback evidence, and blocked reason refs before any connector action can leave plan-only status.",
            [
                "connector_action_promotion_gate_schema_valid",
                "connector_action_promotion_gate_blocks_live_calls",
                "connector_action_promotion_gate_binds_source_fixtures",
                "connector_action_promotion_gate_rejects_authority_drift",
                "connector_action_promotion_gate_rejects_missing_refs",
                "connector_action_promotion_gate_rejects_receipt_ref_and_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "connector_action_promotion_gate_schema_valid": [
                    "connector_action_promotion_gate_passes"
                ],
                "connector_action_promotion_gate_blocks_live_calls": [
                    "connector_action_promotion_gate_passes",
                    "connector_action_promotion_gate_rejects_authority_drift",
                ],
                "connector_action_promotion_gate_binds_source_fixtures": [
                    "connector_action_promotion_gate_passes",
                    "connector_action_promotion_gate_rejects_source_mismatch",
                ],
                "connector_action_promotion_gate_rejects_authority_drift": [
                    "connector_action_promotion_gate_rejects_authority_drift"
                ],
                "connector_action_promotion_gate_rejects_missing_refs": [
                    "connector_action_promotion_gate_rejects_missing_refs"
                ],
                "connector_action_promotion_gate_rejects_receipt_ref_and_count_drift": [
                    "connector_action_promotion_gate_rejects_receipt_ref_and_count_drift"
                ],
            },
        ),
        _surface(
            "readiness_waiver_review_packet",
            [
                "ReadinessWaiverReviewPacket",
                "validate_readiness_waiver_review_packet",
                "readiness_waiver_review_packet.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/readiness_waiver_review_packet.schema.json",
                "examples/readiness_waiver_review_packet.foundation.json",
                "scripts/validate_readiness_waiver_review_packet.py",
                "tests/test_validate_readiness_waiver_review_packet.py",
                "schemas/sdlc_release_candidate.schema.json",
                "schemas/sdlc_deployment_candidate.schema.json",
                "schemas/temporal_accepted_risk_expiry_receipt.schema.json",
                "docs/86_readiness_waiver_review_packet_contract.md",
            ],
            "Readiness waiver review packets bind readiness evidence, target artifact refs, UAO refs, Phi_gov authorization state, approval state, security review state, rollback evidence, accepted-risk status, expiry policy, compensating controls, required evidence refs, and blocked reason refs before any waiver can be reviewed.",
            [
                "readiness_waiver_review_packet_schema_valid",
                "readiness_waiver_review_packet_blocks_readiness_authority",
                "readiness_waiver_review_packet_requires_evidence_refs",
                "readiness_waiver_review_packet_rejects_expiry_drift",
                "readiness_waiver_review_packet_rejects_compensating_control_drift",
                "readiness_waiver_review_packet_rejects_receipt_ref_and_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "readiness_waiver_review_packet_schema_valid": [
                    "readiness_waiver_review_packet_passes"
                ],
                "readiness_waiver_review_packet_blocks_readiness_authority": [
                    "readiness_waiver_review_packet_passes",
                    "readiness_waiver_review_packet_rejects_authority_drift",
                ],
                "readiness_waiver_review_packet_requires_evidence_refs": [
                    "readiness_waiver_review_packet_rejects_missing_refs"
                ],
                "readiness_waiver_review_packet_rejects_expiry_drift": [
                    "readiness_waiver_review_packet_rejects_expiry_drift"
                ],
                "readiness_waiver_review_packet_rejects_compensating_control_drift": [
                    "readiness_waiver_review_packet_rejects_compensating_control_drift"
                ],
                "readiness_waiver_review_packet_rejects_receipt_ref_and_count_drift": [
                    "readiness_waiver_review_packet_rejects_receipt_ref_and_count_drift"
                ],
            },
        ),
        _surface(
            "browser_observation_receipt",
            [
                "BrowserObservationReceipt",
                "validate_browser_observation_receipt",
                "browser_observation_receipt.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/browser_observation_receipt.schema.json",
                "examples/browser_observation_receipt.foundation.json",
                "scripts/validate_browser_observation_receipt.py",
                "tests/test_validate_browser_observation_receipt.py",
                "schemas/capture_policy_decision_ledger.schema.json",
                "schemas/evidence_classification_manifest.schema.json",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "docs/87_browser_observation_receipt_contract.md",
            ],
            "Browser observation receipts bind hash-only URL evidence, DOM digest refs, screenshot digest refs, consent scope, capture policy refs, evidence classification refs, UAO refs, privacy guards, and authority-denial flags before browser inspection can become operator evidence.",
            [
                "browser_observation_receipt_schema_valid",
                "browser_observation_receipt_blocks_browser_authority",
                "browser_observation_receipt_requires_digest_refs",
                "browser_observation_receipt_rejects_raw_storage",
                "browser_observation_receipt_rejects_receipt_ref_and_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "browser_observation_receipt_schema_valid": [
                    "browser_observation_receipt_passes"
                ],
                "browser_observation_receipt_blocks_browser_authority": [
                    "browser_observation_receipt_passes",
                    "browser_observation_receipt_rejects_authority_drift",
                ],
                "browser_observation_receipt_requires_digest_refs": [
                    "browser_observation_receipt_passes",
                    "browser_observation_receipt_rejects_raw_url_and_digest_drift",
                ],
                "browser_observation_receipt_rejects_raw_storage": [
                    "browser_observation_receipt_rejects_raw_storage_drift"
                ],
                "browser_observation_receipt_rejects_receipt_ref_and_count_drift": [
                    "browser_observation_receipt_rejects_receipt_ref_and_count_drift"
                ],
            },
        ),
        _surface(
            "trusted_capture_evidence_packet",
            [
                "TrustedCaptureEvidencePacket",
                "validate_trusted_capture_evidence_packet",
                "trusted_capture_evidence_packet.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/trusted_capture_evidence_packet.schema.json",
                "examples/trusted_capture_evidence_packet.foundation.json",
                "scripts/validate_trusted_capture_evidence_packet.py",
                "tests/test_validate_trusted_capture_evidence_packet.py",
                "schemas/capture_policy_decision_ledger.schema.json",
                "schemas/evidence_classification_manifest.schema.json",
                "schemas/browser_observation_receipt.schema.json",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "docs/89_trusted_capture_evidence_packet_contract.md",
            ],
            "Trusted capture evidence packets bind source-surface hash evidence, capture policy refs, evidence classification refs, browser observation refs, UAO refs, LifeMeaningJudgment refs, digest-only capture artifact refs, privacy guards, and authority-denial flags before capture evidence can become operator evidence.",
            [
                "trusted_capture_evidence_packet_schema_valid",
                "trusted_capture_evidence_packet_blocks_capture_authority",
                "trusted_capture_evidence_packet_requires_digest_refs",
                "trusted_capture_evidence_packet_rejects_raw_media_retention",
                "trusted_capture_evidence_packet_rejects_receipt_ref_and_count_drift",
                "trusted_capture_evidence_packet_sdlc_artifacts_valid",
            ],
            runtime_witness_anchor_aliases={
                "trusted_capture_evidence_packet_schema_valid": [
                    "trusted_capture_evidence_packet_passes"
                ],
                "trusted_capture_evidence_packet_blocks_capture_authority": [
                    "trusted_capture_evidence_packet_passes",
                    "trusted_capture_evidence_packet_rejects_authority_drift",
                ],
                "trusted_capture_evidence_packet_requires_digest_refs": [
                    "trusted_capture_evidence_packet_passes",
                    "trusted_capture_evidence_packet_rejects_digest_and_scope_drift",
                ],
                "trusted_capture_evidence_packet_rejects_raw_media_retention": [
                    "trusted_capture_evidence_packet_rejects_raw_media_retention"
                ],
                "trusted_capture_evidence_packet_rejects_receipt_ref_and_count_drift": [
                    "trusted_capture_evidence_packet_rejects_receipt_ref_and_count_drift"
                ],
                "trusted_capture_evidence_packet_sdlc_artifacts_valid": [
                    "sdlc_requirement_and_design_validate_for_trusted_capture_evidence_packet"
                ],
            },
        ),
        _surface(
            "sccml_trace_adapter_witness",
            [
                "SccmlTraceAdapterWitness",
                "validate_sccml_trace_adapter_witness",
                "sccml_trace_adapter_witness.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/sccml_trace_adapter_witness.schema.json",
                "examples/sccml_trace_adapter_witness.foundation.json",
                "scripts/validate_sccml_trace_adapter_witness.py",
                "tests/test_validate_sccml_trace_adapter_witness.py",
                "schemas/kernel_proof.schema.json",
                "schemas/trace_entry.schema.json",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "docs/90_sccml_trace_adapter_witness_contract.md",
            ],
            "SCCML trace adapter witnesses bind instruction-trace digest refs, pre-state and post-state hash refs, proof digest refs, unsupported-operation gap refs, KernelProof refs, TraceEntry refs, UAO refs, LifeMeaningJudgment refs, integrity guards, and authority-denial flags before SCCML traces can become governance proof.",
            [
                "sccml_trace_adapter_witness_schema_valid",
                "sccml_trace_adapter_witness_blocks_kernel_authority",
                "sccml_trace_adapter_witness_requires_digest_refs",
                "sccml_trace_adapter_witness_rejects_unsupported_op_silence",
                "sccml_trace_adapter_witness_rejects_raw_trace_retention",
                "sccml_trace_adapter_witness_rejects_receipt_ref_and_count_drift",
                "sccml_trace_adapter_witness_sdlc_artifacts_valid",
            ],
            runtime_witness_anchor_aliases={
                "sccml_trace_adapter_witness_schema_valid": [
                    "sccml_trace_adapter_witness_passes"
                ],
                "sccml_trace_adapter_witness_blocks_kernel_authority": [
                    "sccml_trace_adapter_witness_passes",
                    "sccml_trace_adapter_witness_rejects_authority_drift",
                ],
                "sccml_trace_adapter_witness_requires_digest_refs": [
                    "sccml_trace_adapter_witness_passes",
                    "sccml_trace_adapter_witness_rejects_digest_and_scope_drift",
                ],
                "sccml_trace_adapter_witness_rejects_unsupported_op_silence": [
                    "sccml_trace_adapter_witness_rejects_unsupported_op_silence"
                ],
                "sccml_trace_adapter_witness_rejects_raw_trace_retention": [
                    "sccml_trace_adapter_witness_rejects_raw_trace_and_state_retention"
                ],
                "sccml_trace_adapter_witness_rejects_receipt_ref_and_count_drift": [
                    "sccml_trace_adapter_witness_rejects_receipt_ref_and_count_drift"
                ],
                "sccml_trace_adapter_witness_sdlc_artifacts_valid": [
                    "sdlc_requirement_and_design_validate_for_sccml_trace_adapter_witness"
                ],
            },
        ),
        _surface(
            "chaos_rehearsal_execution_report",
            [
                "ChaosRehearsalExecutionReport",
                "validate_chaos_rehearsal_execution_report",
                "chaos_rehearsal_execution_report.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/chaos_rehearsal_execution_report.schema.json",
                "examples/chaos_rehearsal_execution_report.foundation.json",
                "scripts/validate_chaos_rehearsal_execution_report.py",
                "tests/test_validate_chaos_rehearsal_execution_report.py",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "schemas/effect_assurance.schema.json",
                "schemas/simulation_receipt.schema.json",
                "schemas/worker_failure_receipt.schema.json",
                "schemas/sdlc_recovery_handoff_receipt.schema.json",
                "docs/91_chaos_rehearsal_execution_report_contract.md",
            ],
            "Chaos rehearsal execution reports bind scenario refs, invariant refs, injection-point refs, expected containment refs, expected signal refs, required evidence refs, rollback guard refs, result-bank digest refs, UAO refs, LifeMeaningJudgment refs, safety guards, and authority-denial flags before runtime resilience or invariant-fuzz claims can affect staging, production, or canonical runtime state.",
            [
                "chaos_rehearsal_execution_report_schema_valid",
                "chaos_rehearsal_execution_report_blocks_runtime_disruption",
                "chaos_rehearsal_execution_report_requires_scenario_and_rollback_refs",
                "chaos_rehearsal_execution_report_rejects_raw_runtime_retention",
                "chaos_rehearsal_execution_report_rejects_result_count_drift",
                "chaos_rehearsal_execution_report_rejects_receipt_ref_and_count_drift",
                "chaos_rehearsal_execution_report_sdlc_artifacts_valid",
            ],
            runtime_witness_anchor_aliases={
                "chaos_rehearsal_execution_report_schema_valid": [
                    "chaos_rehearsal_execution_report_passes"
                ],
                "chaos_rehearsal_execution_report_blocks_runtime_disruption": [
                    "chaos_rehearsal_execution_report_passes",
                    "chaos_rehearsal_execution_report_rejects_authority_drift",
                    "chaos_rehearsal_execution_report_rejects_live_scope_drift",
                ],
                "chaos_rehearsal_execution_report_requires_scenario_and_rollback_refs": [
                    "chaos_rehearsal_execution_report_rejects_missing_scenario_evidence_and_rollback_refs"
                ],
                "chaos_rehearsal_execution_report_rejects_raw_runtime_retention": [
                    "chaos_rehearsal_execution_report_rejects_raw_runtime_log_retention"
                ],
                "chaos_rehearsal_execution_report_rejects_result_count_drift": [
                    "chaos_rehearsal_execution_report_rejects_result_and_summary_count_drift"
                ],
                "chaos_rehearsal_execution_report_rejects_receipt_ref_and_count_drift": [
                    "chaos_rehearsal_execution_report_rejects_receipt_ref_and_count_drift"
                ],
                "chaos_rehearsal_execution_report_sdlc_artifacts_valid": [
                    "sdlc_requirement_and_design_validate_for_chaos_rehearsal_execution_report"
                ],
            },
        ),
        _surface(
            "invariant_fuzz_execution_report",
            [
                "InvariantFuzzExecutionReport",
                "validate_invariant_fuzz_execution_report",
                "invariant_fuzz_execution_report.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/invariant_fuzz_execution_report.schema.json",
                "examples/invariant_fuzz_execution_report.foundation.json",
                "scripts/validate_invariant_fuzz_execution_report.py",
                "tests/test_validate_invariant_fuzz_execution_report.py",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "schemas/effect_assurance.schema.json",
                "schemas/simulation_receipt.schema.json",
                "schemas/worker_failure_receipt.schema.json",
                "schemas/sdlc_recovery_handoff_receipt.schema.json",
                "docs/92_invariant_fuzz_execution_report_contract.md",
            ],
            "Invariant fuzz execution reports bind deterministic seed refs, case-bank digest refs, mutation-class refs, oracle refs, expected accept and reject counts, projection probe counts, projection leak checks, result-bank digest refs, UAO refs, LifeMeaningJudgment refs, safety guards, and authority-denial flags before runtime-hardening or invariant-fuzz claims can affect staging, production, or canonical runtime state.",
            [
                "invariant_fuzz_execution_report_schema_valid",
                "invariant_fuzz_execution_report_blocks_canonical_mutation",
                "invariant_fuzz_execution_report_requires_case_bank_and_oracles",
                "invariant_fuzz_execution_report_rejects_projection_and_raw_retention",
                "invariant_fuzz_execution_report_rejects_result_count_drift",
                "invariant_fuzz_execution_report_rejects_receipt_ref_and_count_drift",
                "invariant_fuzz_execution_report_sdlc_artifacts_valid",
            ],
            runtime_witness_anchor_aliases={
                "invariant_fuzz_execution_report_schema_valid": [
                    "invariant_fuzz_execution_report_passes"
                ],
                "invariant_fuzz_execution_report_blocks_canonical_mutation": [
                    "invariant_fuzz_execution_report_passes",
                    "invariant_fuzz_execution_report_rejects_authority_drift",
                    "invariant_fuzz_execution_report_rejects_live_scope_drift",
                ],
                "invariant_fuzz_execution_report_requires_case_bank_and_oracles": [
                    "invariant_fuzz_execution_report_rejects_case_bank_and_oracle_drift"
                ],
                "invariant_fuzz_execution_report_rejects_projection_and_raw_retention": [
                    "invariant_fuzz_execution_report_rejects_projection_and_raw_retention_drift"
                ],
                "invariant_fuzz_execution_report_rejects_result_count_drift": [
                    "invariant_fuzz_execution_report_rejects_result_and_summary_count_drift"
                ],
                "invariant_fuzz_execution_report_rejects_receipt_ref_and_count_drift": [
                    "invariant_fuzz_execution_report_rejects_receipt_ref_and_count_drift"
                ],
                "invariant_fuzz_execution_report_sdlc_artifacts_valid": [
                    "sdlc_requirement_and_design_validate_for_invariant_fuzz_execution_report"
                ],
            },
        ),
        _surface(
            "research_source_conflict_map",
            [
                "ResearchSourceConflictMap",
                "validate_research_source_conflict_map",
                "research_source_conflict_map.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/research_source_conflict_map.schema.json",
                "examples/research_source_conflict_map.foundation.json",
                "scripts/validate_research_source_conflict_map.py",
                "tests/test_validate_research_source_conflict_map.py",
                "schemas/search_decision.schema.json",
                "schemas/search_receipt.schema.json",
                "schemas/evidence_classification_manifest.schema.json",
                "schemas/universal_action_orchestration.schema.json",
                "schemas/life_meaning_judgment.schema.json",
                "docs/88_research_source_conflict_map_contract.md",
            ],
            "Research source conflict maps preserve citation-backed source disagreements, contradiction class, freshness impact, follow-up sensing needs, retention guards, and authority-denial flags before research synthesis or retrieval expansion can be considered.",
            [
                "research_source_conflict_map_schema_valid",
                "research_source_conflict_map_blocks_live_research_authority",
                "research_source_conflict_map_requires_citation_bound_conflicts",
                "research_source_conflict_map_rejects_raw_body_retention",
                "research_source_conflict_map_rejects_sensing_authority_drift",
                "research_source_conflict_map_rejects_receipt_ref_and_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "research_source_conflict_map_schema_valid": [
                    "research_source_conflict_map_passes"
                ],
                "research_source_conflict_map_blocks_live_research_authority": [
                    "research_source_conflict_map_passes",
                    "research_source_conflict_map_rejects_authority_drift",
                ],
                "research_source_conflict_map_requires_citation_bound_conflicts": [
                    "research_source_conflict_map_passes",
                    "research_source_conflict_map_rejects_conflict_citation_drift",
                ],
                "research_source_conflict_map_rejects_raw_body_retention": [
                    "research_source_conflict_map_rejects_raw_body_and_digest_drift"
                ],
                "research_source_conflict_map_rejects_sensing_authority_drift": [
                    "research_source_conflict_map_rejects_follow_up_sensing_drift"
                ],
                "research_source_conflict_map_rejects_receipt_ref_and_count_drift": [
                    "research_source_conflict_map_rejects_receipt_ref_and_count_drift"
                ],
            },
        ),
        _surface(
            "worker_receipt_ledger_read_model",
            [
                "WorkerReceiptLedgerReadModel",
                "validate_worker_receipt_ledger_read_model",
                "worker_receipt_ledger_read_model.v1",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "schemas/worker_receipt_ledger_read_model.schema.json",
                "examples/worker_receipt_ledger_read_model.foundation.json",
                "scripts/validate_worker_receipt_ledger_read_model.py",
                "tests/test_validate_worker_receipt_ledger_read_model.py",
                "schemas/worker_failure_receipt.schema.json",
                "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
                "schemas/connector_action_promotion_gate.schema.json",
                "docs/84_worker_receipt_ledger_read_model_contract.md",
                "schemas/universal_action_orchestration.schema.json",
            ],
            "Worker receipt ledger read models project scheduler, lease, read-only worker, runtime receipt, failure, and connector-promotion refs into bounded operator chain summaries while denying live receipt-store reads, worker dispatch, runtime receipt emission, connector calls, writes, terminal closure, and success claims.",
            [
                "worker_receipt_ledger_read_model_schema_valid",
                "worker_receipt_ledger_read_model_blocks_live_authority",
                "worker_receipt_ledger_read_model_rejects_chain_guard_drift",
                "worker_receipt_ledger_read_model_rejects_summary_drift",
                "worker_receipt_ledger_read_model_rejects_missing_refs",
                "worker_receipt_ledger_read_model_sdlc_artifacts_valid",
            ],
            runtime_witness_anchor_aliases={
                "worker_receipt_ledger_read_model_schema_valid": [
                    "worker_receipt_ledger_read_model_passes"
                ],
                "worker_receipt_ledger_read_model_blocks_live_authority": [
                    "worker_receipt_ledger_read_model_passes",
                    "worker_receipt_ledger_read_model_rejects_live_authority",
                ],
                "worker_receipt_ledger_read_model_rejects_chain_guard_drift": [
                    "worker_receipt_ledger_read_model_rejects_chain_guard_drift"
                ],
                "worker_receipt_ledger_read_model_rejects_summary_drift": [
                    "worker_receipt_ledger_read_model_rejects_summary_drift"
                ],
                "worker_receipt_ledger_read_model_rejects_missing_refs": [
                    "worker_receipt_ledger_read_model_rejects_missing_refs"
                ],
                "worker_receipt_ledger_read_model_sdlc_artifacts_valid": [
                    "sdlc_requirement_and_design_validate_for_worker_receipt_ledger_read_model"
                ],
            },
        ),
        _surface(
            "mfidel_substrate_conformance_receipt",
            [
                "MfidelSubstrateConformanceReceipt",
                "validate_mfidel_substrate_conformance_receipt",
                "mfidel_substrate_conformance_receipt.v1",
            ],
            "audit_chain",
            "audit_chain",
            "audit_chain",
            "witnessed",
            [
                "schemas/mfidel_substrate_conformance_receipt.schema.json",
                "examples/mfidel_substrate_conformance_receipt.foundation.json",
                "scripts/validate_mfidel_substrate_conformance_receipt.py",
                "tests/test_validate_mfidel_substrate_conformance_receipt.py",
                "mcoi/mcoi_runtime/substrate/mfidel/grid.py",
                "mcoi/mcoi_runtime/core/mfidel_matrix.py",
                "mcoi/mcoi_runtime/contracts/mfidel.py",
                "mcoi/tests/test_mfidel_atomicity.py",
                "mcoi/tests/test_mfidel_matrix.py",
                "docs/85_mfidel_substrate_conformance_receipt_contract.md",
            ],
            "Mfidel substrate conformance receipts bind local Python substrate digests, grid bounds, exact-preservation witnesses, no-normalization proof refs, and TypeScript/Rust SDK/kernel evidence gaps while denying Unicode normalization, fidel decomposition, live runtime import authority, cross-runtime closure, and terminal closure.",
            [
                "mfidel_substrate_conformance_receipt_schema_valid",
                "mfidel_substrate_conformance_receipt_preserves_atomicity",
                "mfidel_substrate_conformance_receipt_rejects_guard_drift",
                "mfidel_substrate_conformance_receipt_rejects_digest_drift",
                "mfidel_substrate_conformance_receipt_rejects_exact_preservation_drift",
                "mfidel_substrate_conformance_receipt_rejects_cross_runtime_gap_drift",
                "mfidel_substrate_conformance_receipt_sdlc_artifacts_valid",
            ],
            runtime_witness_anchor_aliases={
                "mfidel_substrate_conformance_receipt_schema_valid": [
                    "mfidel_substrate_conformance_receipt_passes"
                ],
                "mfidel_substrate_conformance_receipt_preserves_atomicity": [
                    "mfidel_substrate_conformance_receipt_passes",
                    "mfidel_substrate_conformance_receipt_rejects_decomposed_like_input",
                ],
                "mfidel_substrate_conformance_receipt_rejects_guard_drift": [
                    "mfidel_substrate_conformance_receipt_rejects_atomicity_guard_drift"
                ],
                "mfidel_substrate_conformance_receipt_rejects_digest_drift": [
                    "mfidel_substrate_conformance_receipt_rejects_digest_drift"
                ],
                "mfidel_substrate_conformance_receipt_rejects_exact_preservation_drift": [
                    "mfidel_substrate_conformance_receipt_rejects_exact_preservation_drift"
                ],
                "mfidel_substrate_conformance_receipt_rejects_cross_runtime_gap_drift": [
                    "mfidel_substrate_conformance_receipt_rejects_cross_runtime_gap_drift"
                ],
                "mfidel_substrate_conformance_receipt_sdlc_artifacts_valid": [
                    "sdlc_requirement_and_design_validate_for_mfidel_substrate_conformance_receipt"
                ],
            },
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
            runtime_witness_anchor_aliases={
                "approval_separation_required": [
                    "approval_separation_required",
                    "self_approval_is_blocked",
                ],
                "pending_controls_block_case_closure": [
                    "pending_controls_block_case_closure",
                    "pending_control_blocks_case_closure",
                ],
                "decider_authority_required": [
                    "decider_authority_required",
                    "non_decider_case_closure_is_blocked",
                ],
                "case_closure_not_terminal_command_closure": [
                    "case_closure_not_terminal_command_closure",
                    "resolved_control_allows_non_terminal_closure",
                    "collaboration_closure_rejects_terminal_claim",
                ],
                "collaboration_case_schema_valid": [
                    "collaboration_case_schema_valid",
                    "collaboration_case_schema_export_validates",
                ],
            },
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
            runtime_witness_anchor_aliases={
                "payment_requires_approval_counterexample": [
                    "payment_requires_approval_counterexample"
                ],
                "tenant_isolation_counterexample": [
                    "tenant_isolation_counterexample"
                ],
                "shell_requires_sandbox_counterexample": [
                    "shell_requires_sandbox_counterexample"
                ],
                "provider_url_approved_counterexample": [
                    "provider_url_approved_counterexample"
                ],
                "memory_requires_admission_counterexample": [
                    "memory_requires_admission_counterexample"
                ],
                "unknown_property_fails_closed": [
                    "unknown_property_fails_closed"
                ],
                "policy_proof_report_schema_valid": [
                    "policy_proof_report_schema_valid"
                ],
            },
        ),
        _surface(
            "shell_execution_adapter",
            [
                "ShellExecutor.execute",
                "ShellExecutionReceipt",
                "ShellSandboxPolicy",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/adapters/shell_executor.py",
                "mcoi/mcoi_runtime/contracts/shell_execution.py",
                "mcoi/tests/test_shell_executor.py",
            ],
            "Shell execution is argv-only, policy/sandbox gated, receipt-backed, and exposes shell receipts as actual effects that can close Effect Assurance.",
            [
                "shell_executor_argv_only",
                "shell_policy_denial_receipt_emitted",
                "shell_sandbox_denial_receipt_emitted",
                "shell_receipt_becomes_effect_assurance_evidence_ref",
                "shell_receipt_closes_effect_assurance",
            ],
        ),
        _surface(
            "memory_lattice",
            [
                "MemoryLatticeGate.assess",
                "MemoryLatticeAdmission",
                "P3MemoryTopologyMap",
                "build_p3_memory_topology_read_model",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "gateway/memory_lattice.py",
                "schemas/memory_lattice.schema.json",
                "schemas/p3_memory_topology_read_model.schema.json",
                "tests/test_gateway/test_memory_lattice.py",
            ],
            "Memory lattice admission derives planning and execution use from evidence, learning admission, policy authority, freshness, scope, contradiction state, and bounded P3 topology projections.",
            [
                "raw_event_memory_not_directly_admitted",
                "semantic_memory_requires_learning_admission",
                "policy_memory_requires_authority_ref",
                "preference_memory_tenant_owner_scoped",
                "contradiction_and_stale_memory_block_execution",
                "memory_lattice_schema_valid",
                "p3_memory_topology_binds_refs",
                "p3_memory_topology_read_model_schema_valid",
                "p3_memory_topology_read_model_blocks_authority",
            ],
            runtime_witness_anchor_aliases={
                "raw_event_memory_not_directly_admitted": [
                    "raw_event_memory_is_never_directly_admitted",
                ],
                "semantic_memory_requires_learning_admission": [
                    "semantic_memory_requires_admitted_learning_decision",
                ],
                "policy_memory_requires_authority_ref": [
                    "policy_memory_requires_policy_authority_ref",
                ],
                "preference_memory_tenant_owner_scoped": [
                    "preference_memory_is_tenant_owner_scoped_and_not_execution_authority",
                ],
                "memory_lattice_schema_valid": [
                    "memory_lattice_schema_exposes_admission_claim",
                ],
                "p3_memory_topology_binds_refs": [
                    "p3_topology_map_binds_mind_memory_world_and_evidence_refs",
                ],
                "p3_memory_topology_read_model_schema_valid": [
                    "p3_topology_read_model_projects_bounded_operator_surface",
                    "blocked_p3_topology_read_model_exposes_blockers_without_graph_surface",
                ],
                "p3_memory_topology_read_model_blocks_authority": [
                    "p3_topology_read_model_projects_bounded_operator_surface",
                    "blocked_p3_topology_read_model_exposes_blockers_without_graph_surface",
                ],
            },
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
            runtime_witness_anchor_aliases={
                "repeated_trace_pattern_required": [
                    "workflow_mining_detects_repeated_invoice_pattern",
                    "workflow_mining_ignores_singletons_and_other_tenants",
                ],
                "workflow_draft_activation_blocked": [
                    "workflow_mining_detects_repeated_invoice_pattern",
                    "workflow_draft_rejects_unblocked_activation",
                ],
                "operator_review_required": [
                    "workflow_mining_detects_repeated_invoice_pattern",
                ],
                "sandbox_replay_required": [
                    "workflow_mining_detects_repeated_invoice_pattern",
                ],
                "risky_pattern_requires_approval_rules": [
                    "workflow_mining_projects_governance_for_payment_pattern",
                ],
                "workflow_mining_report_schema_valid": [
                    "workflow_mining_schema_exposes_draft_contract",
                ],
            },
        ),
        _surface(
            "trust_ledger",
            [
                "TrustLedger.issue",
                "TrustLedger.verify",
                "TrustLedger.anchor_bundle",
                "TrustLedger.verify_anchor_receipt",
                "/evidence/bundles/{command_id}",
                "GET /evidence/bundles/{command_id}",
                "scripts/verify_evidence_bundle.py",
                "scripts/verify_anchor_receipt.py",
                "scripts/package_orgos_anchor_export.py",
                "scripts/preflight_trust_ledger_remote_submission.py",
                "scripts/submit_trust_ledger_anchor_export.py",
                "TrustLedger.package_anchor_export",
                "TrustLedgerRemoteSubmissionPreflightReport",
                "TrustLedgerBundle",
                "ExternalProofAnchorReceipt",
                "TrustLedgerExportPackage",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "docs/62_governed_operational_intelligence.md",
                "docs/65_trust_ledger_offline_verification.md",
                "gateway/evidence_bundle.py",
                "gateway/trust_ledger.py",
                "scripts/verify_evidence_bundle.py",
                "scripts/verify_anchor_receipt.py",
                "scripts/package_orgos_anchor_export.py",
                "scripts/preflight_trust_ledger_remote_submission.py",
                "scripts/submit_trust_ledger_anchor_export.py",
                "schemas/trust_ledger_anchor_receipt.schema.json",
                "schemas/trust_ledger_remote_submission_preflight.schema.json",
                "schemas/trust_ledger_anchor_submission_receipt.schema.json",
                "schemas/trust_ledger_anchor_verification_report.schema.json",
                "schemas/trust_ledger_bundle.schema.json",
                "schemas/trust_ledger_bundle_verification_report.schema.json",
                "schemas/trust_ledger_evidence_artifacts.schema.json",
                "schemas/trust_ledger_export_package.schema.json",
                "tests/test_gateway/test_evidence_bundle_endpoint.py",
                "tests/test_gateway/test_trust_ledger_anchor_receipt.py",
                "tests/test_gateway/test_trust_ledger.py",
                "tests/test_verify_anchor_receipt.py",
                "tests/test_package_orgos_anchor_export.py",
                "tests/test_preflight_trust_ledger_remote_submission.py",
                "tests/test_submit_trust_ledger_anchor_export.py",
            ],
            "Trust ledger signs terminal-closure evidence bundles, exposes operator bundle export, verifies exported bundle and anchor receipt files offline, emits external anchor receipts, packages verifier inputs with content hashes for portable audit review, can merge verified optional OrgOS event receipts into terminal anchor exports without replacing closure, emits a read-only canonical remote submission preflight receipt whose identity binds verification and ledger state, and records operator-confirmed external anchor submissions in a signed hash-chained ledger after a matching preflight receipt gates optional HTTPS transparency-log submission and the remote endpoint echoes payload plus receipt hashes.",
            [
                "terminal_command_exports_signed_evidence_bundle",
                "evidence_bundle_endpoint_rejects_non_terminal_command",
                "offline_bundle_verifier_detects_tampering",
                "offline_bundle_verifier_report_contract_allows_missing_secret",
                "trust_ledger_issues_and_verifies_signed_bundle",
                "trust_ledger_detects_tampered_bundle_content",
                "trust_ledger_detects_wrong_secret_signature",
                "trust_ledger_requires_terminal_certificate_and_evidence",
                "trust_ledger_rejects_non_proof_evidence_refs",
                "trust_ledger_requires_anchor_ref_when_anchored",
                "trust_ledger_bundle_schema_exposes_signature_contract",
                "trust_ledger_bundle_schema_rejects_non_proof_evidence_ref",
                "trust_ledger_anchor_receipt_binds_required_artifacts",
                "trust_ledger_anchor_receipt_detects_tampered_artifact_root",
                "trust_ledger_anchor_receipt_rejects_missing_terminal_artifact",
                "trust_ledger_anchor_receipt_rejects_non_proof_artifact_evidence_ref",
                "trust_ledger_anchor_receipt_rejects_command_identity_drift",
                "trust_ledger_anchor_receipt_rejects_non_canonical_receipt_id",
                "trust_ledger_anchor_receipt_validates_against_schema",
                "trust_ledger_anchor_receipt_schema_rejects_non_canonical_bundle_id",
                "trust_ledger_export_package_binds_verifier_inputs",
                "trust_ledger_export_package_rejects_receipt_identity_drift",
                "verify_anchor_receipt_files_accepts_valid_export",
                "verify_anchor_receipt_files_detects_tampered_artifact_root",
                "verify_anchor_receipt_files_rejects_schema_invalid_receipt",
                "verify_anchor_receipt_files_rejects_schema_invalid_artifacts",
                "verify_anchor_receipt_files_detects_package_bundle_hash_mismatch",
                "verify_anchor_receipt_files_rejects_schema_invalid_package",
                "verify_anchor_receipt_files_rejects_package_hash_mismatch",
                "verify_anchor_receipt_cli_reports_valid_export",
                "verify_anchor_receipt_report_contract_allows_missing_secret_report",
                "package_orgos_anchor_export_merges_optional_orgos_artifact",
                "package_orgos_anchor_export_rejects_required_orgos_artifact",
                "package_orgos_anchor_export_rejects_missing_terminal_artifact",
                "package_orgos_anchor_export_blocks_invalid_generated_package_before_publish",
                "package_orgos_anchor_export_rolls_back_partial_publish_failure",
                "package_orgos_anchor_export_restores_existing_files_on_publish_failure",
                "package_orgos_anchor_export_cli_emits_verifiable_package",
                "trust_ledger_remote_submission_preflight_accepts_ready_export",
                "trust_ledger_remote_submission_preflight_projects_final_submit_payload_hash",
                "trust_ledger_remote_submission_preflight_blocks_missing_remote_token",
                "trust_ledger_remote_submission_preflight_blocks_nonfinite_remote_timeout",
                "trust_ledger_remote_submission_preflight_blocks_tampered_package",
                "trust_ledger_remote_submission_preflight_cli_writes_schema_checked_receipt",
                "trust_ledger_remote_submission_preflight_writer_validates_schema",
                "submit_trust_ledger_anchor_export_records_signed_submission",
                "submit_trust_ledger_anchor_export_blocks_without_confirmation",
                "submit_trust_ledger_anchor_export_blocks_when_submission_ledger_locked",
                "submit_trust_ledger_anchor_export_does_not_accept_boolean_lock_bypass",
                "submit_trust_ledger_anchor_export_removes_stale_submission_ledger_lock",
                "submit_trust_ledger_anchor_export_blocks_invalid_submission_ledger_lock_config",
                "submit_trust_ledger_anchor_export_blocks_unbounded_operator_id",
                "submit_trust_ledger_anchor_export_blocks_tampered_package",
                "submit_trust_ledger_anchor_export_posts_remote_transparency_log",
                "submit_trust_ledger_anchor_export_blocks_remote_without_confirmation",
                "submit_trust_ledger_anchor_export_blocks_remote_transport_when_submission_ledger_locked",
                "submit_trust_ledger_anchor_export_requires_remote_preflight_receipt",
                "submit_trust_ledger_anchor_export_blocks_invalid_remote_timeout_before_transport",
                "submit_trust_ledger_anchor_export_blocks_remote_preflight_hash_mismatch",
                "submit_trust_ledger_anchor_export_blocks_remote_preflight_receipt_id_mismatch",
                "submit_trust_ledger_anchor_export_blocks_remote_preflight_anchor_state_drift",
                "submit_trust_ledger_anchor_export_blocks_remote_preflight_ledger_state_drift",
                "submit_trust_ledger_anchor_export_blocks_remote_preflight_checked_at_drift",
                "submit_trust_ledger_anchor_export_blocks_nonfinite_remote_preflight_timeout",
                "submit_trust_ledger_anchor_export_blocks_remote_hash_mismatch",
                "submit_trust_ledger_anchor_export_blocks_missing_remote_receipt_hash",
                "submit_trust_ledger_anchor_export_blocks_malformed_remote_receipt_hash",
                "verify_submission_ledger_detects_hash_drift",
                "submit_trust_ledger_anchor_export_cli_emits_submission_receipt",
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
                "/operator/physical-capability-promotion-receipts",
                "/operator/physical-capability-promotion-receipts/console",
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
                "gateway/server.py",
                "gateway/physical_action_boundary.py",
                "gateway/physical_capability_promotion_receipt.py",
                "gateway/physical_capability_promotion_store.py",
                "gateway/physical_worker_canary.py",
                "scripts/emit_physical_capability_promotion_receipt.py",
                "scripts/preflight_physical_capability_promotion.py",
                "scripts/produce_physical_worker_canary.py",
                "schemas/physical_action_receipt.schema.json",
                "schemas/physical_capability_promotion_receipt.schema.json",
                "tests/test_emit_physical_capability_promotion_receipt.py",
                "tests/test_gateway/test_capability_capsule_installer.py",
                "tests/test_gateway/test_physical_action_boundary.py",
                "tests/test_gateway/test_physical_capability_pack.py",
                "tests/test_gateway/test_physical_capability_promotion_receipt.py",
                "tests/test_gateway/test_physical_worker_canary.py",
                "tests/test_preflight_physical_capability_promotion.py",
                "tests/test_produce_physical_worker_canary.py",
            ],
            "Physical action boundary emits schema-backed pre-dispatch receipts that block physical-world side effects unless hardware identity, safety envelope, manual override, emergency stop, simulation, operator approval, sensor confirmation, and safe-state controls are present; checked-in physical capability fixtures stay outside default loading, admit sandbox replay only when production readiness is not required, reject live physical promotion by default, and require promotion preflight evidence before any live production claim.",
            [
                "physical_boundary_allows_sandbox_replay_with_full_controls",
                "physical_boundary_blocks_without_simulation",
                "physical_boundary_blocks_live_effects_without_certification",
                "physical_boundary_requires_operator_review_when_approval_missing",
                "physical_action_receipt_matches_schema",
                "physical_fixture_pack_is_not_loaded_by_default",
                "physical_fixture_pack_allows_sandbox_replay_when_production_gate_disabled",
                "physical_fixture_pack_blocks_live_promotion_when_production_gate_enabled",
                "physical_fixture_pack_projects_sandbox_only_gateway_evidence",
                "physical_capability_promotion_preflight_blocks_live_fixture_by_default",
                "physical_capability_promotion_preflight_passes_with_full_evidence",
                "physical_capability_promotion_preflight_allows_sandbox_only_pack",
                "physical_capability_promotion_preflight_cli_outputs_json",
                "capsule_installer_runs_physical_preflight_before_registry_mutation",
                "capsule_installer_returns_rejected_receipt_without_registry_mutation",
                "capsule_installer_admits_physical_capsule_when_preflight_passes",
                "capsule_admission_operator_endpoint_blocks_physical_preflight_failure",
                "capsule_admission_operator_endpoint_accepts_physical_safety_refs_from_handoff",
                "physical_capability_promotion_receipt_binds_ready_chain",
                "operator_physical_promotion_receipt_endpoint_emits_ready_bundle",
                "operator_physical_promotion_receipt_endpoint_persists_jsonl_ledger",
                "operator_physical_promotion_receipt_console_renders_ledger",
                "operator_physical_promotion_receipt_endpoint_blocks_missing_live_refs",
                "physical_promotion_receipt_jsonl_store_lists_newest_with_filters",
                "physical_promotion_receipt_jsonl_store_fails_closed_on_invalid_record",
                "emit_physical_capability_promotion_receipt_accepts_fixture_refs",
                "emit_physical_capability_promotion_receipt_blocks_missing_refs",
                "emit_physical_capability_promotion_receipt_blocks_missing_physical_safety_refs",
                "emit_physical_capability_promotion_receipt_cli_outputs_json",
                "emit_physical_capability_promotion_receipt_cli_strict_blocks_missing_refs",
                "physical_worker_canary_blocks_missing_receipt_and_allows_sandbox_replay",
                "physical_worker_canary_artifact_preserves_no_effect_proof",
                "physical_worker_canary_evidence_and_hash_are_stable",
                "produce_physical_worker_canary_writes_artifact",
                "physical_worker_canary_cli_strict_passes",
            ],
        ),
        _surface(
            "temporal_kernel",
            [
                "/api/v1/temporal/schedules",
                "/api/v1/temporal/schedules/{schedule_id}",
                "/api/v1/temporal/schedules/{schedule_id}/cancel",
                "/api/v1/temporal/schedules/{schedule_id}/lease/reclaim",
                "/api/v1/temporal/schedules/{schedule_id}/missed",
                "/api/v1/temporal/worker/tick",
                "/api/v1/temporal/monitor",
                "/api/v1/temporal/summary",
                "TemporalKernel.evaluate",
                "TrustedClock.now_utc",
                "TrustedClock.monotonic_ns",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
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
                "temporal_monitor_is_read_only",
                "schedule_read_models_persisted",
                "worker_tick_certifies_proofs",
                "cancel_emits_terminal_receipt",
                "expired_lease_reclaim_emits_repair_receipt",
                "missed_emits_terminal_receipt",
                "temporal_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_injected": [
                    "temporal_kernel_allows_due_fresh_schema_valid_receipt"
                ],
                "monotonic_duration_measured": [
                    "temporal_kernel_allows_due_fresh_schema_valid_receipt"
                ],
                "future_schedule_defers": [
                    "temporal_kernel_defers_future_execution_without_terminal_closure"
                ],
                "approval_expiry_denies": ["temporal_kernel_denies_expired_approval"],
                "stale_evidence_escalates": ["temporal_kernel_escalates_stale_evidence"],
                "budget_window_checked": [
                    "temporal_kernel_denies_missing_causal_precondition_and_budget_window"
                ],
                "causal_preconditions_required": [
                    "temporal_kernel_denies_missing_causal_precondition_and_budget_window"
                ],
                "temporal_scheduler_routes_governed": [
                    "default_routers_include_temporal_scheduler_summary"
                ],
                "temporal_monitor_is_read_only": [
                    "temporal_monitor_reports_due_lease_and_expiry_without_mutation",
                    "temporal_monitor_filters_by_tenant",
                ],
                "schedule_read_models_persisted": [
                    "create_list_and_get_temporal_schedule"
                ],
                "worker_tick_certifies_proofs": [
                    "worker_tick_runs_due_schedule_and_returns_proofs"
                ],
                "cancel_emits_terminal_receipt": [
                    "cancel_temporal_schedule_records_terminal_receipt"
                ],
                "expired_lease_reclaim_emits_repair_receipt": [
                    "reclaim_expired_temporal_lease_records_repair_receipt"
                ],
                "missed_emits_terminal_receipt": [
                    "missed_temporal_schedule_records_terminal_receipt"
                ],
                "temporal_receipt_schema_valid": [
                    "temporal_kernel_allows_due_fresh_schema_valid_receipt"
                ],
                "receipt_not_terminal_closure": [
                    "temporal_kernel_defers_future_execution_without_terminal_closure"
                ],
            },
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
            runtime_witness_anchor_aliases={
                "evidence_age_computed_from_runtime_clock": [
                    "evidence_freshness_allows_fresh_required_schema_receipt"
                ],
                "freshness_window_required_for_dispatch": [
                    "freshness_window_required_for_dispatch"
                ],
                "stale_required_evidence_triggers_refresh": [
                    "evidence_freshness_requires_refresh_for_stale_required_type"
                ],
                "missing_required_evidence_blocks_dispatch": [
                    "evidence_freshness_blocks_missing_required_evidence"
                ],
                "revoked_or_unverified_high_risk_evidence_blocks": [
                    "evidence_freshness_blocks_revoked_unverified_or_wrong_tenant_evidence"
                ],
                "expiring_evidence_warns_before_dispatch": [
                    "evidence_freshness_warns_when_evidence_is_expiring_soon"
                ],
                "temporal_evidence_freshness_receipt_schema_valid": [
                    "evidence_freshness_allows_fresh_required_schema_receipt"
                ],
                "receipt_not_terminal_closure": [
                    "evidence_freshness_allows_fresh_required_schema_receipt"
                ],
            },
        ),
        _surface(
            "temporal_resolution",
            [
                "evaluate_temporal_resolution",
                "TemporalResolutionRequest",
                "TemporalResolutionReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_resolution.py",
                "schemas/temporal_resolution_receipt.schema.json",
                "tests/test_gateway/test_temporal_resolution.py",
            ],
            "Temporal resolution receipts resolve bounded temporal phrases with runtime-owned time truth, tenant timezone preservation, original text retention, business-calendar defaults, unsupported phrase closure, and high-risk clarification before scheduling or dispatch.",
            [
                "runtime_clock_owns_phrase_resolution",
                "original_text_preserved",
                "tenant_timezone_controls_local_resolution",
                "relative_duration_resolved_from_injected_now",
                "ambiguous_low_risk_phrase_uses_safe_default",
                "ambiguous_high_risk_phrase_requires_clarification",
                "business_day_resolution_skips_weekends_and_holidays",
                "unsupported_phrase_fails_closed",
                "temporal_resolution_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_phrase_resolution": [
                    "temporal_resolution_resolves_relative_duration_from_runtime_now"
                ],
                "original_text_preserved": [
                    "temporal_resolution_resolves_tomorrow_explicit_time_in_tenant_timezone"
                ],
                "tenant_timezone_controls_local_resolution": [
                    "temporal_resolution_resolves_tomorrow_explicit_time_in_tenant_timezone"
                ],
                "relative_duration_resolved_from_injected_now": [
                    "temporal_resolution_resolves_relative_duration_from_runtime_now"
                ],
                "ambiguous_low_risk_phrase_uses_safe_default": [
                    "temporal_resolution_low_risk_ambiguous_tomorrow_uses_safe_default"
                ],
                "ambiguous_high_risk_phrase_requires_clarification": [
                    "temporal_resolution_high_risk_ambiguous_tomorrow_requires_clarification"
                ],
                "business_day_resolution_skips_weekends_and_holidays": [
                    "temporal_resolution_business_days_skip_weekend_and_holiday"
                ],
                "unsupported_phrase_fails_closed": [
                    "temporal_resolution_unsupported_phrase_fails_closed"
                ],
                "temporal_resolution_receipt_schema_valid": [
                    "temporal_resolution_resolves_relative_duration_from_runtime_now"
                ],
                "receipt_not_terminal_closure": [
                    "temporal_resolution_resolves_relative_duration_from_runtime_now"
                ],
            },
        ),
        _surface(
            "temporal_sla",
            [
                "/api/v1/sla",
                "/api/v1/sla/violations",
                "TemporalSla.evaluate",
                "SlaPolicy",
                "SlaCase",
                "TemporalSlaReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_sla.py",
                "mcoi/mcoi_runtime/app/routers/data/sla.py",
                "mcoi/mcoi_runtime/core/sla_monitor.py",
                "schemas/temporal_sla_receipt.schema.json",
                "tests/test_gateway/test_temporal_sla.py",
                "mcoi/tests/test_sla_monitor.py",
                "mcoi/tests/test_sla_router.py",
            ],
            "Temporal SLA surfaces expose governed SLA summaries and violation read models while temporal SLA receipts certify business calendars, business-time deadlines, warning escalation, breach detection, tenant scope, evidence refs, and dispatch windows before escalation or action.",
            [
                "runtime_clock_owns_sla_deadlines",
                "business_time_deadlines_skip_closed_windows",
                "approaching_deadline_warns_before_breach",
                "breached_deadline_emits_escalation_reason",
                "outside_business_window_holds_normal_dispatch",
                "sla_evidence_and_scope_checked",
                "sla_summary_read_model_bounded",
                "sla_violations_read_model_bounded",
                "temporal_sla_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_sla_deadlines": [
                    "temporal_sla_allows_on_track_schema_valid_receipt"
                ],
                "business_time_deadlines_skip_closed_windows": [
                    "temporal_sla_business_time_skips_closed_window"
                ],
                "approaching_deadline_warns_before_breach": [
                    "temporal_sla_warns_when_response_deadline_approaches"
                ],
                "breached_deadline_emits_escalation_reason": [
                    "temporal_sla_breaches_response_deadline"
                ],
                "outside_business_window_holds_normal_dispatch": [
                    "temporal_sla_holds_normal_dispatch_outside_business_window"
                ],
                "sla_evidence_and_scope_checked": [
                    "temporal_sla_blocks_missing_evidence_and_high_severity_contacts"
                ],
                "sla_summary_read_model_bounded": [
                    "sla_summary_endpoint_returns_bounded_governed_read_model"
                ],
                "sla_violations_read_model_bounded": [
                    "sla_violations_endpoint_filters_by_sla_id"
                ],
                "temporal_sla_receipt_schema_valid": [
                    "temporal_sla_allows_on_track_schema_valid_receipt"
                ],
                "receipt_not_terminal_closure": [
                    "temporal_sla_allows_on_track_schema_valid_receipt"
                ],
            },
        ),
        _surface(
            "temporal_reapproval",
            [
                "TemporalReapproval.evaluate",
                "ReapprovalRequest",
                "TemporalReapprovalReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_reapproval.py",
                "schemas/temporal_reapproval_receipt.schema.json",
                "tests/test_gateway/test_temporal_reapproval.py",
            ],
            "Temporal reapproval rechecks high-risk and critical approval grants at execution time for expiry, revocation, scope, tenant, approver role coverage, approval age, evidence refs, and source schedule binding before dispatch.",
            [
                "runtime_clock_owns_reapproval_time",
                "high_risk_approval_roles_required",
                "expired_approval_requires_reapproval",
                "revoked_or_out_of_scope_approval_blocks_dispatch",
                "missing_approval_role_requires_reapproval",
                "low_risk_action_does_not_require_reapproval",
                "temporal_reapproval_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_reapproval_time": [
                    "temporal_reapproval_approves_valid_high_risk_grants_schema_receipt",
                ],
                "high_risk_approval_roles_required": [
                    "temporal_reapproval_requires_missing_role_coverage",
                ],
                "expired_approval_requires_reapproval": [
                    "temporal_reapproval_requires_fresh_approval_when_grant_expired",
                ],
                "revoked_or_out_of_scope_approval_blocks_dispatch": [
                    "temporal_reapproval_blocks_invalid_or_unsafe_grants",
                ],
                "missing_approval_role_requires_reapproval": [
                    "temporal_reapproval_requires_missing_role_coverage",
                ],
                "low_risk_action_does_not_require_reapproval": [
                    "temporal_reapproval_marks_low_risk_action_not_required",
                ],
                "temporal_reapproval_receipt_schema_valid": [
                    "temporal_reapproval_approves_valid_high_risk_grants_schema_receipt",
                ],
                "receipt_not_terminal_closure": [
                    "temporal_reapproval_approves_valid_high_risk_grants_schema_receipt",
                ],
            },
        ),
        _surface(
            "temporal_dispatch_window",
            [
                "TemporalDispatchWindow.evaluate",
                "DispatchWindowRequest",
                "TemporalDispatchWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_dispatch_window.py",
                "schemas/temporal_dispatch_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_dispatch_window.py",
            ],
            "Temporal dispatch window rechecks tenant-local dispatch admission at runtime through allowed windows, blackout windows, holidays, evidence refs, and high-risk source schedule plus reapproval binding before worker execution.",
            [
                "runtime_clock_owns_dispatch_window_time",
                "tenant_timezone_resolved",
                "allowed_window_required_for_high_risk_dispatch",
                "outside_allowed_window_defers_dispatch",
                "active_blackout_defers_dispatch",
                "holiday_closure_defers_dispatch",
                "source_reapproval_bound_for_high_risk_dispatch",
                "temporal_dispatch_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_dispatch_window_time": [
                    "dispatch_window_allows_high_risk_action_inside_allowed_window"
                ],
                "tenant_timezone_resolved": [
                    "dispatch_window_allows_high_risk_action_inside_allowed_window"
                ],
                "allowed_window_required_for_high_risk_dispatch": [
                    "dispatch_window_blocks_invalid_high_risk_policy_state",
                    "dispatch_window_marks_low_risk_action_not_required",
                ],
                "outside_allowed_window_defers_dispatch": [
                    "dispatch_window_defers_outside_allowed_window_to_next_business_window"
                ],
                "active_blackout_defers_dispatch": [
                    "dispatch_window_defers_active_blackout_inside_allowed_window"
                ],
                "holiday_closure_defers_dispatch": [
                    "dispatch_window_defers_holiday_to_next_business_window"
                ],
                "source_reapproval_bound_for_high_risk_dispatch": [
                    "dispatch_window_allows_high_risk_action_inside_allowed_window",
                    "dispatch_window_blocks_invalid_high_risk_policy_state",
                ],
                "temporal_dispatch_window_receipt_schema_valid": [
                    "dispatch_window_allows_high_risk_action_inside_allowed_window"
                ],
                "receipt_not_terminal_closure": [
                    "dispatch_window_allows_high_risk_action_inside_allowed_window"
                ],
            },
        ),
        _surface(
            "temporal_budget_window",
            [
                "TemporalBudgetWindow.evaluate",
                "BudgetWindowRequest",
                "TemporalBudgetWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_budget_window.py",
                "schemas/temporal_budget_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_budget_window.py",
            ],
            "Temporal budget window rechecks tenant-local daily, weekly, monthly, or custom reset periods against active spend snapshots, reserved spend, projected spend, evidence refs, and high-risk source receipts before worker execution.",
            [
                "runtime_clock_owns_budget_window_time",
                "tenant_timezone_resolves_budget_period",
                "daily_weekly_monthly_budget_resets_computed",
                "spend_snapshot_period_matches_active_window",
                "projected_spend_blocks_over_limit_dispatch",
                "future_budget_window_defers_dispatch",
                "source_reapproval_bound_for_high_risk_budget_window",
                "temporal_budget_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_budget_window_time": [
                    "budget_window_allows_high_risk_action_inside_daily_remaining_budget"
                ],
                "tenant_timezone_resolves_budget_period": [
                    "budget_window_allows_high_risk_action_inside_daily_remaining_budget",
                    "budget_window_preserves_weekly_tenant_local_reset_window",
                ],
                "daily_weekly_monthly_budget_resets_computed": [
                    "budget_window_allows_high_risk_action_inside_daily_remaining_budget",
                    "budget_window_preserves_weekly_tenant_local_reset_window",
                ],
                "spend_snapshot_period_matches_active_window": [
                    "budget_window_blocks_mismatched_snapshot_and_missing_sources"
                ],
                "projected_spend_blocks_over_limit_dispatch": [
                    "budget_window_blocks_when_projected_spend_exceeds_active_limit"
                ],
                "future_budget_window_defers_dispatch": [
                    "budget_window_defers_future_custom_period"
                ],
                "source_reapproval_bound_for_high_risk_budget_window": [
                    "budget_window_allows_high_risk_action_inside_daily_remaining_budget",
                    "budget_window_blocks_mismatched_snapshot_and_missing_sources",
                ],
                "temporal_budget_window_receipt_schema_valid": [
                    "budget_window_allows_high_risk_action_inside_daily_remaining_budget"
                ],
                "receipt_not_terminal_closure": [
                    "budget_window_allows_high_risk_action_inside_daily_remaining_budget"
                ],
            },
        ),
        _surface(
            "temporal_causal_order",
            [
                "TemporalCausalOrder.evaluate",
                "TemporalCausalOrderRequest",
                "TemporalCausalOrderReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_causal_order.py",
                "schemas/temporal_causal_order_receipt.schema.json",
                "tests/test_gateway/test_temporal_causal_order.py",
            ],
            "Temporal causal order rechecks required timestamped events, tenant and command scope, predecessor edges, source receipts, missing events, and out-of-order events before worker execution.",
            [
                "runtime_clock_owns_causal_order_time",
                "required_events_must_be_present",
                "tenant_and_command_scope_checked",
                "predecessor_edges_checked",
                "out_of_order_events_block_dispatch",
                "future_events_block_dispatch",
                "high_risk_source_receipts_bound",
                "temporal_causal_order_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_causal_order_time": [
                    "causal_order_allows_high_risk_dispatch_when_required_events_are_ordered"
                ],
                "required_events_must_be_present": [
                    "causal_order_blocks_missing_required_event_type"
                ],
                "tenant_and_command_scope_checked": [
                    "causal_order_blocks_invalid_scope_future_event_predecessor_and_missing_sources"
                ],
                "predecessor_edges_checked": [
                    "causal_order_blocks_invalid_scope_future_event_predecessor_and_missing_sources",
                    "causal_order_blocks_out_of_order_runtime_timestamps",
                ],
                "out_of_order_events_block_dispatch": [
                    "causal_order_blocks_out_of_order_runtime_timestamps"
                ],
                "future_events_block_dispatch": [
                    "causal_order_blocks_invalid_scope_future_event_predecessor_and_missing_sources"
                ],
                "high_risk_source_receipts_bound": [
                    "causal_order_allows_high_risk_dispatch_when_required_events_are_ordered",
                    "causal_order_blocks_invalid_scope_future_event_predecessor_and_missing_sources",
                ],
                "temporal_causal_order_receipt_schema_valid": [
                    "causal_order_allows_high_risk_dispatch_when_required_events_are_ordered"
                ],
                "receipt_not_terminal_closure": [
                    "causal_order_allows_high_risk_dispatch_when_required_events_are_ordered"
                ],
            },
        ),
        _surface(
            "temporal_monotonic_duration",
            [
                "TemporalMonotonicDuration.evaluate",
                "TemporalMonotonicDurationRequest",
                "TemporalMonotonicDurationReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_monotonic_duration.py",
                "schemas/temporal_monotonic_duration_receipt.schema.json",
                "tests/test_gateway/test_temporal_monotonic_duration.py",
            ],
            "Temporal monotonic duration rechecks timeout, latency, cooldown, retry-delay, and watchdog elapsed time from monotonic clock readings before dispatch.",
            [
                "runtime_monotonic_clock_owns_duration_truth",
                "wall_clock_not_used_for_duration",
                "duration_limit_exceeded_blocks_dispatch",
                "cooldown_lower_bound_defers_dispatch",
                "monotonic_clock_regression_blocks_dispatch",
                "high_risk_source_receipts_bound",
                "temporal_monotonic_duration_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_monotonic_clock_owns_duration_truth": [
                    "monotonic_duration_allows_high_risk_dispatch_inside_latency_bound",
                ],
                "wall_clock_not_used_for_duration": [
                    "monotonic_duration_allows_high_risk_dispatch_inside_latency_bound",
                ],
                "duration_limit_exceeded_blocks_dispatch": [
                    "monotonic_duration_blocks_when_timeout_limit_is_exceeded",
                ],
                "cooldown_lower_bound_defers_dispatch": [
                    "monotonic_duration_defers_cooldown_until_lower_bound_elapsed",
                ],
                "monotonic_clock_regression_blocks_dispatch": [
                    "monotonic_duration_blocks_regressed_clock_scope_evidence_and_missing_sources",
                ],
                "high_risk_source_receipts_bound": [
                    "monotonic_duration_blocks_regressed_clock_scope_evidence_and_missing_sources",
                ],
                "temporal_monotonic_duration_receipt_schema_valid": [
                    "monotonic_duration_allows_high_risk_dispatch_inside_latency_bound",
                ],
                "receipt_not_terminal_closure": [
                    "monotonic_duration_allows_high_risk_dispatch_inside_latency_bound",
                ],
            },
        ),
        _surface(
            "temporal_accepted_risk_expiry",
            [
                "TemporalAcceptedRiskExpiry.evaluate",
                "TemporalAcceptedRiskRequest",
                "TemporalAcceptedRiskExpiryReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_accepted_risk_expiry.py",
                "schemas/temporal_accepted_risk_expiry_receipt.schema.json",
                "tests/test_gateway/test_temporal_accepted_risk_expiry.py",
            ],
            "Temporal accepted-risk expiry rechecks active accepted-risk records for expiry, lifecycle disposition, tenant and command scope, review obligation, owner, evidence refs, and source receipts before dispatch reuse.",
            [
                "runtime_clock_owns_accepted_risk_expiry",
                "expired_accepted_risk_blocks_dispatch",
                "revoked_or_closed_accepted_risk_blocks_dispatch",
                "tenant_command_and_action_scope_checked",
                "review_obligation_required",
                "accepted_risk_evidence_refs_required",
                "high_risk_source_receipts_bound",
                "temporal_accepted_risk_expiry_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_accepted_risk_expiry": [
                    "accepted_risk_expiry_allows_high_risk_active_unexpired_record"
                ],
                "expired_accepted_risk_blocks_dispatch": [
                    "accepted_risk_expiry_blocks_expired_record"
                ],
                "revoked_or_closed_accepted_risk_blocks_dispatch": [
                    "accepted_risk_expiry_blocks_revoked_and_closed_records"
                ],
                "tenant_command_and_action_scope_checked": [
                    "accepted_risk_expiry_blocks_wrong_scope_missing_evidence_and_sources"
                ],
                "review_obligation_required": [
                    "accepted_risk_grant_requires_review_obligation"
                ],
                "accepted_risk_evidence_refs_required": [
                    "accepted_risk_expiry_blocks_wrong_scope_missing_evidence_and_sources"
                ],
                "high_risk_source_receipts_bound": [
                    "accepted_risk_expiry_allows_high_risk_active_unexpired_record",
                    "accepted_risk_expiry_blocks_wrong_scope_missing_evidence_and_sources",
                ],
                "temporal_accepted_risk_expiry_receipt_schema_valid": [
                    "accepted_risk_expiry_allows_high_risk_active_unexpired_record"
                ],
                "receipt_not_terminal_closure": [
                    "accepted_risk_expiry_allows_high_risk_active_unexpired_record"
                ],
            },
        ),
        _surface(
            "temporal_credential_expiry",
            [
                "TemporalCredentialExpiry.evaluate",
                "TemporalCredentialRequest",
                "TemporalCredentialExpiryReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_credential_expiry.py",
                "schemas/temporal_credential_expiry_receipt.schema.json",
                "tests/test_gateway/test_temporal_credential_expiry.py",
            ],
            "Temporal credential expiry rechecks connector credential descriptors for expiry, lifecycle disposition, provider and credential scope, rotation warning windows, owner, evidence refs, source binding receipts, and no-secret serialization before dispatch.",
            [
                "runtime_clock_owns_credential_expiry",
                "expired_credentials_block_dispatch",
                "revoked_credentials_block_dispatch",
                "provider_and_credential_scope_checked",
                "rotation_pending_warns_before_dispatch",
                "rotation_overdue_blocks_dispatch",
                "credential_evidence_refs_required",
                "secret_value_absence_verified",
                "high_risk_source_receipts_bound",
                "temporal_credential_expiry_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_credential_expiry": [
                    "credential_expiry_allows_high_risk_active_scoped_unexpired_credential",
                    "credential_expiry_blocks_expired_credential",
                ],
                "expired_credentials_block_dispatch": [
                    "credential_expiry_blocks_expired_credential"
                ],
                "revoked_credentials_block_dispatch": [
                    "credential_expiry_blocks_wrong_scope_revoked_missing_evidence_and_sources"
                ],
                "provider_and_credential_scope_checked": [
                    "credential_expiry_blocks_wrong_scope_revoked_missing_evidence_and_sources"
                ],
                "rotation_pending_warns_before_dispatch": [
                    "credential_expiry_marks_near_expiry_as_rotation_pending"
                ],
                "rotation_overdue_blocks_dispatch": [
                    "credential_expiry_blocks_future_or_rotation_overdue_credential"
                ],
                "credential_evidence_refs_required": [
                    "credential_expiry_blocks_wrong_scope_revoked_missing_evidence_and_sources"
                ],
                "secret_value_absence_verified": [
                    "credential_expiry_rejects_secret_material_in_metadata"
                ],
                "high_risk_source_receipts_bound": [
                    "credential_expiry_allows_high_risk_active_scoped_unexpired_credential",
                    "credential_expiry_blocks_wrong_scope_revoked_missing_evidence_and_sources",
                ],
                "temporal_credential_expiry_receipt_schema_valid": [
                    "credential_expiry_allows_high_risk_active_scoped_unexpired_credential",
                    "credential_expiry_marks_low_risk_action_not_required",
                ],
                "receipt_not_terminal_closure": [
                    "credential_expiry_marks_low_risk_action_not_required",
                    "credential_expiry_allows_high_risk_active_scoped_unexpired_credential",
                ],
            },
        ),
        _surface(
            "temporal_retention_window",
            [
                "TemporalRetentionWindow.evaluate",
                "TemporalRetentionRequest",
                "TemporalRetentionWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_retention_window.py",
                "schemas/temporal_retention_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_retention_window.py",
            ],
            "Temporal retention window rechecks data lifecycle actions for retention_until, delete_after, legal hold, tenant scope, owner, retention policy refs, evidence refs, source data decisions, retention approval, backup guard evidence, and overdue timing before deletion, archive, anonymization, or retention review.",
            [
                "runtime_clock_owns_retention_timing",
                "delete_before_delete_after_defers_action",
                "archive_and_anonymize_wait_for_retention_until",
                "legal_hold_blocks_lifecycle_action",
                "overdue_retention_action_warns",
                "tenant_scope_checked",
                "retention_policy_ref_required",
                "subject_evidence_refs_required",
                "high_risk_source_receipts_bound",
                "retention_approval_and_backup_guard_bound",
                "temporal_retention_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_retention_timing": [
                    "retention_window_allows_delete_at_due_boundary",
                    "retention_window_blocks_invalid_or_future_record",
                ],
                "delete_before_delete_after_defers_action": [
                    "retention_window_defers_delete_before_delete_after"
                ],
                "archive_and_anonymize_wait_for_retention_until": [
                    "retention_window_allows_archive_after_retention_until"
                ],
                "legal_hold_blocks_lifecycle_action": [
                    "retention_window_blocks_legal_hold_wrong_tenant_missing_evidence_and_sources"
                ],
                "overdue_retention_action_warns": [
                    "retention_window_marks_overdue_after_warning_window"
                ],
                "tenant_scope_checked": [
                    "retention_window_blocks_legal_hold_wrong_tenant_missing_evidence_and_sources"
                ],
                "retention_policy_ref_required": [
                    "retention_window_blocks_invalid_or_future_record",
                    "retention_window_blocks_legal_hold_wrong_tenant_missing_evidence_and_sources",
                ],
                "subject_evidence_refs_required": [
                    "retention_window_blocks_legal_hold_wrong_tenant_missing_evidence_and_sources"
                ],
                "high_risk_source_receipts_bound": [
                    "retention_window_allows_archive_after_retention_until",
                    "retention_window_blocks_legal_hold_wrong_tenant_missing_evidence_and_sources",
                ],
                "retention_approval_and_backup_guard_bound": [
                    "retention_window_allows_delete_at_due_boundary",
                    "retention_window_blocks_due_delete_without_retention_approval",
                ],
                "temporal_retention_window_receipt_schema_valid": [
                    "retention_window_allows_delete_at_due_boundary",
                    "retention_window_marks_low_risk_action_not_required",
                ],
                "receipt_not_terminal_closure": [
                    "retention_window_marks_low_risk_action_not_required",
                    "retention_window_allows_delete_at_due_boundary",
                ],
            },
        ),
        _surface(
            "github_check_run_write_receipts",
            [
                "GitHubCheckRunWriter.evaluate",
                "GitHubCheckRunWriteRequest",
                "GitHubCheckRunWriteReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/github_check_run_writer.py",
                "schemas/github_check_run_write_receipt.schema.json",
                "tests/test_gateway/test_github_check_run_writer.py",
            ],
            "GitHub check-run write receipts build hash-bound Checks API payloads, preserve plan-only and dry-run no-write modes, and require approval, installation, external execution, response id, and response hash evidence before a write-approved external check-run claim is admitted.",
            [
                "check_run_payload_is_hash_bound",
                "plan_only_does_not_write_check_run",
                "dry_run_rejects_response_evidence",
                "write_approved_requires_github_app_execution_receipt",
                "write_approved_binds_external_execution_receipt",
                "secret_value_absence_verified",
                "completed_status_requires_conclusion",
                "github_check_run_write_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "check_run_payload_is_hash_bound": [
                    "github_check_run_plan_only_builds_hash_bound_payload"
                ],
                "plan_only_does_not_write_check_run": [
                    "github_check_run_plan_only_builds_hash_bound_payload"
                ],
                "dry_run_rejects_response_evidence": [
                    "github_check_run_dry_run_rejects_response_evidence"
                ],
                "write_approved_requires_github_app_execution_receipt": [
                    "github_check_run_write_approved_requires_github_app_execution_receipt"
                ],
                "write_approved_binds_external_execution_receipt": [
                    "github_check_run_write_approved_binds_external_execution_receipt"
                ],
                "secret_value_absence_verified": [
                    "github_check_run_rejects_secret_value_disclosure"
                ],
                "completed_status_requires_conclusion": [
                    "github_check_run_completed_status_requires_conclusion"
                ],
                "github_check_run_write_receipt_schema_valid": [
                    "github_check_run_plan_only_builds_hash_bound_payload",
                    "github_check_run_write_approved_binds_external_execution_receipt",
                ],
            },
        ),
        _surface(
            "github_app_token_exchange_receipts",
            [
                "GitHubAppTokenExchange.evaluate",
                "GitHubAppTokenExchangeRequest",
                "GitHubAppTokenExchangeReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/github_app_token_exchange.py",
                "schemas/github_app_token_exchange_receipt.schema.json",
                "tests/test_gateway/test_github_app_token_exchange.py",
            ],
            "GitHub App token-exchange receipts build hash-bound installation-token request payloads, preserve plan-only and dry-run no-exchange modes, and require approval, external exchange execution, 2xx response, token fingerprint, token expiry, and response hash evidence before an exchange-approved token claim is admitted.",
            [
                "token_exchange_payload_is_hash_bound",
                "plan_only_does_not_exchange_token",
                "dry_run_rejects_token_response_evidence",
                "exchange_approved_requires_external_receipt",
                "exchange_approved_binds_external_receipt",
                "secret_token_absence_verified",
                "token_ttl_bounds_enforced",
                "github_app_token_exchange_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "token_exchange_payload_is_hash_bound": [
                    "github_app_token_exchange_plan_only_builds_hash_bound_payload"
                ],
                "plan_only_does_not_exchange_token": [
                    "github_app_token_exchange_plan_only_builds_hash_bound_payload"
                ],
                "dry_run_rejects_token_response_evidence": [
                    "github_app_token_exchange_dry_run_rejects_response_evidence"
                ],
                "exchange_approved_requires_external_receipt": [
                    "github_app_token_exchange_approved_requires_external_receipt"
                ],
                "exchange_approved_binds_external_receipt": [
                    "github_app_token_exchange_approved_binds_external_receipt"
                ],
                "secret_token_absence_verified": [
                    "github_app_token_exchange_rejects_raw_token_disclosure"
                ],
                "token_ttl_bounds_enforced": [
                    "github_app_token_exchange_rejects_invalid_ttl_before_planning"
                ],
                "github_app_token_exchange_receipt_schema_valid": [
                    "github_app_token_exchange_plan_only_builds_hash_bound_payload",
                    "github_app_token_exchange_approved_binds_external_receipt",
                ],
            },
        ),
        _surface(
            "github_action_execution_receipts",
            [
                "GitHubActionExecution.evaluate",
                "GitHubActionExecutionRequest",
                "GitHubActionExecutionReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/github_action_execution.py",
                "schemas/github_action_execution_receipt.schema.json",
                "tests/test_gateway/test_github_action_execution.py",
            ],
            "GitHub action execution receipts bind GitHub REST action payloads to token-plan repository identity, preserve plan-only and dry-run no-execution modes, and require approval, token-exchange receipt, external execution receipt, 2xx response, and response hash evidence before an execute-approved external action claim is admitted.",
            [
                "github_action_payload_is_hash_bound",
                "plan_only_does_not_execute_github_action",
                "dry_run_rejects_execution_response_evidence",
                "execute_approved_requires_token_and_external_receipts",
                "execute_approved_binds_external_execution_receipt",
                "token_plan_repository_mismatch_blocks_execution",
                "secret_token_absence_verified",
                "branch_protection_reconcile_action_is_endpoint_bound",
                "github_action_execution_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "github_action_payload_is_hash_bound": [
                    "github_action_execution_plan_only_builds_hash_bound_payload"
                ],
                "plan_only_does_not_execute_github_action": [
                    "github_action_execution_plan_only_builds_hash_bound_payload"
                ],
                "dry_run_rejects_execution_response_evidence": [
                    "github_action_execution_dry_run_rejects_execution_evidence"
                ],
                "execute_approved_requires_token_and_external_receipts": [
                    "github_action_execute_approved_requires_token_and_external_receipts"
                ],
                "execute_approved_binds_external_execution_receipt": [
                    "github_action_execute_approved_binds_external_execution_receipt"
                ],
                "token_plan_repository_mismatch_blocks_execution": [
                    "github_action_execution_blocks_token_plan_repository_mismatch"
                ],
                "secret_token_absence_verified": [
                    "github_action_execution_rejects_secret_value_disclosure"
                ],
                "branch_protection_reconcile_action_is_endpoint_bound": [
                    "branch_protection_reconcile_action_is_endpoint_bound"
                ],
                "github_action_execution_receipt_schema_valid": [
                    "github_action_execution_plan_only_builds_hash_bound_payload",
                    "github_action_execute_approved_binds_external_execution_receipt",
                ],
            },
        ),
        _surface(
            "github_branch_protection_reconcile_receipts",
            [
                "BranchProtectionReconciler.evaluate",
                "BranchProtectionReconcileRequest",
                "BranchProtectionReconcileReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/branch_protection_reconcile.py",
                "schemas/github_branch_protection_reconcile_receipt.schema.json",
                "tests/test_gateway/test_branch_protection_reconcile.py",
            ],
            "GitHub branch-protection reconcile receipts compare desired branch policy to observed protection state, bind the protected-branch REST payload and plan hash, preserve plan-only and dry-run no-apply modes, and require approval, token-exchange receipt, action-execution receipt, 2xx response, and response hash evidence before an apply-approved external reconcile claim is admitted.",
            [
                "branch_protection_policy_payload_is_hash_bound",
                "observed_compliance_emits_noop_receipt",
                "observed_drift_emits_reconcile_actions",
                "missing_observed_state_is_explicit",
                "dry_run_rejects_apply_response_evidence",
                "apply_approved_requires_external_receipts",
                "apply_approved_binds_external_action_receipt",
                "noop_apply_blocks_external_mutation",
                "secret_value_absence_verified",
                "github_branch_protection_reconcile_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "branch_protection_policy_payload_is_hash_bound": [
                    "branch_protection_reconcile_noop_is_hash_bound",
                    "branch_protection_payload_uses_checks_objects",
                ],
                "observed_compliance_emits_noop_receipt": [
                    "branch_protection_reconcile_noop_is_hash_bound"
                ],
                "observed_drift_emits_reconcile_actions": [
                    "branch_protection_reconcile_plan_reports_observed_drift"
                ],
                "missing_observed_state_is_explicit": [
                    "branch_protection_reconcile_plan_marks_missing_observed_state"
                ],
                "dry_run_rejects_apply_response_evidence": [
                    "branch_protection_reconcile_dry_run_rejects_apply_evidence"
                ],
                "apply_approved_requires_external_receipts": [
                    "branch_protection_apply_approved_requires_external_receipts"
                ],
                "apply_approved_binds_external_action_receipt": [
                    "branch_protection_apply_approved_binds_external_action_receipt"
                ],
                "noop_apply_blocks_external_mutation": [
                    "branch_protection_apply_approved_blocks_noop_apply"
                ],
                "secret_value_absence_verified": [
                    "branch_protection_reconcile_rejects_secret_value_disclosure"
                ],
                "github_branch_protection_reconcile_receipt_schema_valid": [
                    "branch_protection_reconcile_noop_is_hash_bound",
                    "branch_protection_apply_approved_binds_external_action_receipt",
                ],
            },
        ),
        _surface(
            "distributed_lease_claim_receipts",
            [
                "DistributedLeaseClaimPlanner.evaluate",
                "DistributedLeaseClaimBoundaryRequest",
                "DistributedLeaseClaimReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/distributed_lease_boundary.py",
                "schemas/distributed_lease_claim_receipt.schema.json",
                "tests/test_gateway/test_distributed_lease_boundary.py",
            ],
            "Distributed lease claim receipts bind scheduler job identity, worker identity, backend kind, request payload hash, operation payload hash, plan hash, lease expiry, fencing token, adapter claim receipt refs, response evidence, no-secret serialization, and no-local-lease-service-call flags before any distributed scheduler lease claim is admitted.",
            [
                "distributed_lease_policy_and_request_hash_bound",
                "backend_operation_payload_is_hash_bound",
                "plan_only_does_not_claim_lease",
                "dry_run_rejects_claim_response_evidence",
                "claim_approved_requires_external_receipts",
                "claim_approved_binds_adapter_receipt",
                "claim_approved_allows_unfenced_policy_without_token",
                "claim_approved_classifies_conflict_response",
                "claim_approved_classifies_deferred_response",
                "claim_approved_classifies_rejected_response",
                "observed_payload_mismatch_blocks_claim",
                "expired_or_unfenced_claim_blocks_dispatch",
                "secret_value_absence_verified",
                "distributed_lease_claim_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "distributed_lease_policy_and_request_hash_bound": [
                    "distributed_lease_plan_is_hash_bound_and_non_live"
                ],
                "backend_operation_payload_is_hash_bound": [
                    "distributed_lease_plan_is_hash_bound_and_non_live",
                    "distributed_lease_external_gateway_operation_is_endpoint_bound",
                ],
                "plan_only_does_not_claim_lease": [
                    "distributed_lease_plan_is_hash_bound_and_non_live"
                ],
                "dry_run_rejects_claim_response_evidence": [
                    "distributed_lease_dry_run_rejects_claim_response_evidence"
                ],
                "claim_approved_requires_external_receipts": [
                    "distributed_lease_claim_approved_requires_external_receipts"
                ],
                "claim_approved_binds_adapter_receipt": [
                    "distributed_lease_claim_approved_binds_adapter_receipt"
                ],
                "claim_approved_allows_unfenced_policy_without_token": [
                    "distributed_lease_claim_allows_unfenced_policy_without_token"
                ],
                "claim_approved_classifies_conflict_response": [
                    "distributed_lease_claim_classifies_conflict_response"
                ],
                "claim_approved_classifies_deferred_response": [
                    "distributed_lease_claim_classifies_deferred_response"
                ],
                "claim_approved_classifies_rejected_response": [
                    "distributed_lease_claim_classifies_rejected_response"
                ],
                "observed_payload_mismatch_blocks_claim": [
                    "distributed_lease_claim_blocks_observed_payload_mismatch"
                ],
                "expired_or_unfenced_claim_blocks_dispatch": [
                    "distributed_lease_claim_blocks_expired_or_unfenced_grant"
                ],
                "secret_value_absence_verified": [
                    "distributed_lease_claim_rejects_secret_value_disclosure"
                ],
                "distributed_lease_claim_receipt_schema_valid": [
                    "distributed_lease_plan_is_hash_bound_and_non_live",
                    "distributed_lease_claim_approved_binds_adapter_receipt",
                ],
            },
        ),
        _surface(
            "distributed_lease_adapter_registry_receipts",
            [
                "DistributedLeaseAdapterRegistryEvaluator.evaluate",
                "DistributedLeaseAdapterRegistry",
                "DistributedLeaseAdapterRegistryReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/distributed_lease_adapters.py",
                "gateway/distributed_lease_boundary.py",
                "schemas/distributed_lease_adapter_registry_receipt.schema.json",
                "tests/test_gateway/test_distributed_lease_adapters.py",
            ],
            "Distributed lease adapter registry receipts bind backend capability, adapter mode, production readiness, fencing-token support, compare-and-swap support, registry hash, capability hash, and distributed lease claim receipt hash before any adapter claim can be treated as ready, delegated, or blocked.",
            [
                "adapter_registry_default_inventory_hash_bound",
                "adapter_registry_delegates_external_gateway_without_local_execution",
                "adapter_registry_blocks_native_adapter_without_production_readiness",
                "adapter_registry_blocks_fencing_required_backend_without_token_support",
                "adapter_registry_blocks_claim_receipt_violations",
                "adapter_registry_binds_claim_approved_external_gateway_receipt",
                "adapter_registry_rejects_secret_values",
                "distributed_lease_adapter_registry_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "adapter_registry_default_inventory_hash_bound": [
                    "adapter_registry_default_inventory_is_hash_bound"
                ],
                "adapter_registry_delegates_external_gateway_without_local_execution": [
                    "adapter_registry_delegates_external_gateway_without_local_execution"
                ],
                "adapter_registry_blocks_native_adapter_without_production_readiness": [
                    "adapter_registry_blocks_native_adapter_without_production_readiness"
                ],
                "adapter_registry_blocks_fencing_required_backend_without_token_support": [
                    "adapter_registry_blocks_fencing_required_backend_without_token_support"
                ],
                "adapter_registry_blocks_claim_receipt_violations": [
                    "adapter_registry_blocks_claim_receipt_violations_before_capability_admission"
                ],
                "adapter_registry_binds_claim_approved_external_gateway_receipt": [
                    "adapter_registry_binds_claim_approved_external_gateway_receipt"
                ],
                "adapter_registry_rejects_secret_values": [
                    "adapter_registry_rejects_secret_values_in_capability_metadata"
                ],
                "distributed_lease_adapter_registry_receipt_schema_valid": [
                    "adapter_registry_default_inventory_is_hash_bound",
                    "adapter_registry_binds_claim_approved_external_gateway_receipt",
                ],
            },
        ),
        _surface(
            "distributed_lease_execution_receipts",
            [
                "DistributedLeaseExecutionReceiptEvaluator.evaluate",
                "DistributedLeaseExecutionPlan",
                "DistributedLeaseExecutionReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/distributed_lease_execution.py",
                "gateway/distributed_lease_adapters.py",
                "gateway/distributed_lease_boundary.py",
                "schemas/distributed_lease_execution_receipt.schema.json",
                "tests/test_gateway/test_distributed_lease_execution.py",
            ],
            "Distributed lease execution receipts compose adapter registry and claim receipts into a hash-bound execution plan, then classify the boundary as ready, delegated, or blocked while proving no local lease service call, backend adapter call, scheduler mutation, worker dispatch, request authentication, or raw secret storage occurred.",
            [
                "execution_receipt_ready_for_sqlite_compare_and_swap",
                "execution_receipt_delegates_external_gateway_without_http_call",
                "execution_blocks_native_adapter_without_production_readiness",
                "execution_blocks_claim_receipt_violations_before_dispatch",
                "execution_binds_claim_approved_external_gateway_grant",
                "execution_blocks_fencing_required_backend_without_token_support",
                "execution_rejects_secret_value_disclosure",
                "distributed_lease_execution_receipt_schema_valid",
            ],
            runtime_witness_anchor_aliases={
                "execution_receipt_ready_for_sqlite_compare_and_swap": [
                    "execution_receipt_ready_for_sqlite_compare_and_swap_without_live_call"
                ],
                "execution_receipt_delegates_external_gateway_without_http_call": [
                    "execution_receipt_delegates_external_gateway_without_http_call"
                ],
                "execution_blocks_native_adapter_without_production_readiness": [
                    "execution_blocks_native_adapter_without_production_readiness"
                ],
                "execution_blocks_claim_receipt_violations_before_dispatch": [
                    "execution_blocks_claim_receipt_violations_before_dispatch"
                ],
                "execution_binds_claim_approved_external_gateway_grant": [
                    "execution_binds_claim_approved_external_gateway_grant"
                ],
                "execution_blocks_fencing_required_backend_without_token_support": [
                    "execution_blocks_fencing_required_backend_without_token_support"
                ],
                "execution_rejects_secret_value_disclosure": [
                    "execution_rejects_secret_value_disclosure"
                ],
                "distributed_lease_execution_receipt_schema_valid": [
                    "execution_receipt_ready_for_sqlite_compare_and_swap_without_live_call",
                    "execution_binds_claim_approved_external_gateway_grant",
                ],
            },
        ),
        _surface(
            "scheduler_worker_runtime_receipt_handoff",
            [
                "SchedulerWorkerRuntimeReceiptHandoff",
                "validate_scheduler_worker_runtime_receipt_handoff",
                "scheduler_worker_runtime_receipt_handoff.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
                "examples/scheduler_worker_runtime_receipt_handoff.foundation.json",
                "scripts/validate_scheduler_worker_runtime_receipt_handoff.py",
                "tests/test_validate_scheduler_worker_runtime_receipt_handoff.py",
            ],
            "Scheduler worker runtime receipt handoffs bind TemporalSchedulerReceipt and DistributedLeaseExecutionReceipt refs to future worker runtime receipt obligations while denying scheduler dispatch, runtime dispatch, worker invocation, backend calls, filesystem writes, connector authority, terminal closure, and success claims.",
            [
                "scheduler_worker_runtime_handoff_schema_valid",
                "scheduler_worker_runtime_handoff_blocks_live_dispatch",
                "scheduler_worker_runtime_handoff_binds_scheduler_and_lease_receipts",
                "scheduler_worker_runtime_handoff_rejects_authority_drift",
                "scheduler_worker_runtime_handoff_rejects_missing_required_refs",
                "scheduler_worker_runtime_handoff_rejects_admission_and_result_drift",
                "scheduler_worker_runtime_handoff_rejects_receipt_ref_and_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "scheduler_worker_runtime_handoff_schema_valid": [
                    "scheduler_worker_runtime_receipt_handoff_passes"
                ],
                "scheduler_worker_runtime_handoff_blocks_live_dispatch": [
                    "scheduler_worker_runtime_receipt_handoff_passes",
                    "handoff_rejects_admission_and_result_drift",
                ],
                "scheduler_worker_runtime_handoff_binds_scheduler_and_lease_receipts": [
                    "scheduler_worker_runtime_receipt_handoff_passes",
                    "handoff_rejects_top_level_and_contract_drift",
                ],
                "scheduler_worker_runtime_handoff_rejects_authority_drift": [
                    "handoff_rejects_authority_drift"
                ],
                "scheduler_worker_runtime_handoff_rejects_missing_required_refs": [
                    "handoff_rejects_missing_required_refs"
                ],
                "scheduler_worker_runtime_handoff_rejects_admission_and_result_drift": [
                    "handoff_rejects_admission_and_result_drift"
                ],
                "scheduler_worker_runtime_handoff_rejects_receipt_ref_and_count_drift": [
                    "handoff_rejects_receipt_ref_and_count_drift"
                ],
            },
        ),
        _surface(
            "scheduler_worker_runtime_receipt_emitter_dry_run",
            [
                "SchedulerWorkerRuntimeReceiptEmitterDryRun",
                "validate_scheduler_worker_runtime_receipt_emitter_dry_run",
                "scheduler_worker_runtime_receipt_emitter_dry_run.v1",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/scheduler_worker_runtime_receipt_emitter_dry_run.schema.json",
                "examples/scheduler_worker_runtime_receipt_emitter_dry_run.foundation.json",
                "scripts/validate_scheduler_worker_runtime_receipt_emitter_dry_run.py",
                "tests/test_validate_scheduler_worker_runtime_receipt_emitter_dry_run.py",
            ],
            "Scheduler worker runtime receipt emitter dry-runs bind SchedulerWorkerRuntimeReceiptHandoff evidence into a simulated future runtime receipt emitter envelope while denying scheduler dispatch, runtime registration, runtime dispatch, worker invocation, backend calls, filesystem writes, connector authority, runtime receipt emission, worker mesh dispatch receipt emission, terminal closure, and success claims.",
            [
                "scheduler_worker_runtime_emitter_dry_run_schema_valid",
                "scheduler_worker_runtime_emitter_dry_run_blocks_live_dispatch",
                "scheduler_worker_runtime_emitter_dry_run_binds_handoff_receipts",
                "scheduler_worker_runtime_emitter_dry_run_rejects_authority_drift",
                "scheduler_worker_runtime_emitter_dry_run_rejects_missing_required_refs",
                "scheduler_worker_runtime_emitter_dry_run_rejects_result_and_admission_drift",
                "scheduler_worker_runtime_emitter_dry_run_rejects_receipt_ref_and_count_drift",
            ],
            runtime_witness_anchor_aliases={
                "scheduler_worker_runtime_emitter_dry_run_schema_valid": [
                    "scheduler_worker_runtime_receipt_emitter_dry_run_passes"
                ],
                "scheduler_worker_runtime_emitter_dry_run_blocks_live_dispatch": [
                    "scheduler_worker_runtime_receipt_emitter_dry_run_passes",
                    "emitter_dry_run_rejects_result_and_admission_drift",
                ],
                "scheduler_worker_runtime_emitter_dry_run_binds_handoff_receipts": [
                    "scheduler_worker_runtime_receipt_emitter_dry_run_passes",
                    "emitter_dry_run_rejects_top_level_and_contract_drift",
                ],
                "scheduler_worker_runtime_emitter_dry_run_rejects_authority_drift": [
                    "emitter_dry_run_rejects_authority_drift"
                ],
                "scheduler_worker_runtime_emitter_dry_run_rejects_missing_required_refs": [
                    "emitter_dry_run_rejects_missing_required_refs"
                ],
                "scheduler_worker_runtime_emitter_dry_run_rejects_result_and_admission_drift": [
                    "emitter_dry_run_rejects_result_and_admission_drift"
                ],
                "scheduler_worker_runtime_emitter_dry_run_rejects_receipt_ref_and_count_drift": [
                    "emitter_dry_run_rejects_receipt_ref_and_count_drift"
                ],
            },
        ),
        _surface(
            "temporal_rate_limit_window",
            [
                "TemporalRateLimitWindow.evaluate",
                "RateLimitWindowRequest",
                "TemporalRateLimitWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_rate_limit_window.py",
                "schemas/temporal_rate_limit_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_rate_limit_window.py",
            ],
            "Temporal rate-limit window rechecks tenant, endpoint, and identity scoped token windows with runtime-owned reset timing, projected token consumption, burst limits, retry-after timing, evidence refs, and high-risk source receipts before dispatch.",
            [
                "runtime_clock_owns_rate_limit_window",
                "tenant_endpoint_identity_scope_checked",
                "active_window_admits_sufficient_tokens",
                "exhausted_window_emits_retry_after",
                "future_window_defers_dispatch",
                "burst_limit_blocks_overlarge_request",
                "stale_rate_limit_snapshot_blocks_dispatch",
                "high_risk_source_receipts_bound",
                "temporal_rate_limit_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_rate_limit_window": [
                    "rate_limit_window_allows_active_window_with_sufficient_tokens"
                ],
                "tenant_endpoint_identity_scope_checked": [
                    "rate_limit_window_blocks_scope_mismatch_missing_evidence_sources_and_burst"
                ],
                "active_window_admits_sufficient_tokens": [
                    "rate_limit_window_allows_active_window_with_sufficient_tokens"
                ],
                "exhausted_window_emits_retry_after": [
                    "rate_limit_window_throttles_exhausted_window_with_retry_after"
                ],
                "future_window_defers_dispatch": [
                    "rate_limit_window_defers_future_window_until_start"
                ],
                "burst_limit_blocks_overlarge_request": [
                    "rate_limit_window_blocks_scope_mismatch_missing_evidence_sources_and_burst"
                ],
                "stale_rate_limit_snapshot_blocks_dispatch": [
                    "rate_limit_window_blocks_expired_or_invalid_snapshot"
                ],
                "high_risk_source_receipts_bound": [
                    "rate_limit_window_blocks_scope_mismatch_missing_evidence_sources_and_burst"
                ],
                "temporal_rate_limit_window_receipt_schema_valid": [
                    "rate_limit_window_allows_active_window_with_sufficient_tokens"
                ],
                "receipt_not_terminal_closure": [
                    "rate_limit_window_allows_active_window_with_sufficient_tokens"
                ],
            },
        ),
        _surface(
            "temporal_retry_window",
            [
                "TemporalRetryWindow.evaluate",
                "RetryWindowRequest",
                "TemporalRetryWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_retry_window.py",
                "schemas/temporal_retry_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_retry_window.py",
            ],
            "Temporal retry window rechecks retry-after timing, cooldown windows, max attempts, retry expiry, tenant and command scope, evidence refs, and high-risk source receipts before repeated dispatch.",
            [
                "runtime_clock_owns_retry_window",
                "retry_after_floor_checked",
                "cooldown_window_defers_early_retry",
                "max_attempts_block_exhausted_retry",
                "expired_retry_window_blocks_dispatch",
                "tenant_command_scope_checked",
                "terminal_failure_blocks_retry",
                "high_risk_source_receipts_bound",
                "temporal_retry_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_retry_window": [
                    "retry_window_allows_eligible_retry_after_cooldown"
                ],
                "retry_after_floor_checked": [
                    "retry_window_blocks_scope_mismatch_missing_evidence_sources_and_bad_floor"
                ],
                "cooldown_window_defers_early_retry": [
                    "retry_window_defers_before_retry_after_due_time"
                ],
                "max_attempts_block_exhausted_retry": [
                    "retry_window_blocks_exhausted_attempt_budget"
                ],
                "expired_retry_window_blocks_dispatch": [
                    "retry_window_blocks_expired_or_terminal_retry_state"
                ],
                "tenant_command_scope_checked": [
                    "retry_window_blocks_scope_mismatch_missing_evidence_sources_and_bad_floor"
                ],
                "terminal_failure_blocks_retry": [
                    "retry_window_blocks_expired_or_terminal_retry_state"
                ],
                "high_risk_source_receipts_bound": [
                    "retry_window_blocks_scope_mismatch_missing_evidence_sources_and_bad_floor"
                ],
                "temporal_retry_window_receipt_schema_valid": [
                    "retry_window_allows_eligible_retry_after_cooldown"
                ],
                "receipt_not_terminal_closure": [
                    "retry_window_allows_eligible_retry_after_cooldown"
                ],
            },
        ),
        _surface(
            "temporal_lease_window",
            [
                "TemporalLeaseWindow.evaluate",
                "LeaseWindowRequest",
                "TemporalLeaseWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_lease_window.py",
                "schemas/temporal_lease_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_lease_window.py",
            ],
            "Temporal lease window rechecks lease ownership, tenant and command scope, resource scope, worker ownership, fencing tokens, expiry, renewal warning windows, evidence refs, and high-risk source receipts before worker dispatch.",
            [
                "runtime_clock_owns_lease_window",
                "tenant_command_resource_worker_scope_checked",
                "active_lease_admits_dispatch",
                "near_expiry_lease_requires_renewal_warning",
                "expired_lease_blocks_dispatch",
                "released_or_revoked_lease_blocks_dispatch",
                "fencing_token_required",
                "high_risk_source_receipts_bound",
                "temporal_lease_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_lease_window": [
                    "lease_window_allows_active_scoped_lease"
                ],
                "tenant_command_resource_worker_scope_checked": [
                    "lease_window_blocks_scope_mismatch_missing_evidence_fencing_and_closed_lease"
                ],
                "active_lease_admits_dispatch": [
                    "lease_window_allows_active_scoped_lease"
                ],
                "near_expiry_lease_requires_renewal_warning": [
                    "lease_window_warns_when_lease_is_inside_renewal_grace_window"
                ],
                "expired_lease_blocks_dispatch": [
                    "lease_window_blocks_expired_lease_without_dispatch"
                ],
                "released_or_revoked_lease_blocks_dispatch": [
                    "lease_window_blocks_scope_mismatch_missing_evidence_fencing_and_closed_lease"
                ],
                "fencing_token_required": [
                    "lease_window_blocks_scope_mismatch_missing_evidence_fencing_and_closed_lease"
                ],
                "high_risk_source_receipts_bound": [
                    "lease_window_blocks_scope_mismatch_missing_evidence_fencing_and_closed_lease"
                ],
                "temporal_lease_window_receipt_schema_valid": [
                    "lease_window_allows_active_scoped_lease"
                ],
                "receipt_not_terminal_closure": [
                    "lease_window_allows_active_scoped_lease"
                ],
            },
        ),
        _surface(
            "temporal_idempotency_window",
            [
                "TemporalIdempotencyWindow.evaluate",
                "IdempotencyWindowRequest",
                "TemporalIdempotencyWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_idempotency_window.py",
                "schemas/temporal_idempotency_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_idempotency_window.py",
            ],
            "Temporal idempotency window rechecks idempotency keys, request fingerprints, replay windows, tenant and command scope, action scope, committed effects, terminal receipt binding, evidence refs, and high-risk source receipts before effect dispatch.",
            [
                "runtime_clock_owns_idempotency_window",
                "new_idempotency_key_admits_dispatch",
                "matching_replay_admits_uncommitted_dispatch",
                "committed_effect_blocks_duplicate_dispatch",
                "expired_idempotency_window_blocks_dispatch",
                "request_fingerprint_mismatch_blocks_replay",
                "tenant_command_action_scope_checked",
                "high_risk_source_receipts_bound",
                "temporal_idempotency_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_idempotency_window": [
                    "idempotency_window_admits_new_key_with_runtime_window"
                ],
                "new_idempotency_key_admits_dispatch": [
                    "idempotency_window_admits_new_key_with_runtime_window"
                ],
                "matching_replay_admits_uncommitted_dispatch": [
                    "idempotency_window_admits_matching_uncommitted_replay"
                ],
                "committed_effect_blocks_duplicate_dispatch": [
                    "idempotency_window_blocks_duplicate_committed_effect_without_dispatch"
                ],
                "expired_idempotency_window_blocks_dispatch": [
                    "idempotency_window_blocks_expired_replay_window"
                ],
                "request_fingerprint_mismatch_blocks_replay": [
                    "idempotency_window_blocks_scope_fingerprint_evidence_and_source_gaps"
                ],
                "tenant_command_action_scope_checked": [
                    "idempotency_window_blocks_scope_fingerprint_evidence_and_source_gaps"
                ],
                "high_risk_source_receipts_bound": [
                    "idempotency_window_blocks_scope_fingerprint_evidence_and_source_gaps"
                ],
                "temporal_idempotency_window_receipt_schema_valid": [
                    "idempotency_window_admits_new_key_with_runtime_window"
                ],
                "receipt_not_terminal_closure": [
                    "idempotency_window_admits_new_key_with_runtime_window"
                ],
            },
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
            runtime_witness_anchor_aliases={
                "memory_age_computed_from_runtime_clock": [
                    "temporal_memory_allows_fresh_valid_schema_receipt"
                ],
                "stale_memory_requires_refresh": [
                    "temporal_memory_requires_refresh_for_stale_evidence"
                ],
                "validity_window_blocks_expired_memory": [
                    "temporal_memory_blocks_expired_forbidden_high_risk_use"
                ],
                "superseded_memory_not_usable": [
                    "temporal_memory_blocks_superseded_record_without_deleting_history"
                ],
                "confidence_decay_blocks_weak_memory": [
                    "temporal_memory_blocks_when_confidence_decays_below_minimum"
                ],
                "tenant_owner_scope_checked": [
                    "temporal_memory_blocks_tenant_and_owner_scope_mismatch"
                ],
                "allowed_use_checked": [
                    "temporal_memory_blocks_expired_forbidden_high_risk_use"
                ],
                "temporal_memory_receipt_schema_valid": [
                    "temporal_memory_allows_fresh_valid_schema_receipt"
                ],
                "receipt_not_terminal_closure": [
                    "temporal_memory_allows_fresh_valid_schema_receipt"
                ],
            },
        ),
        _surface(
            "temporal_missed_run",
            [
                "evaluate_temporal_missed_run",
                "MissedRunRequest",
                "TemporalMissedRunReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_missed_run.py",
                "schemas/temporal_missed_run_receipt.schema.json",
                "tests/test_gateway/test_temporal_missed_run.py",
            ],
            "Temporal missed-run receipts classify late, expired, duplicate-dispatched, and recovery-due scheduled commands with runtime-owned time truth, scheduler source receipts, evidence refs, and high-risk reapproval binding before skip, retry, or closure.",
            [
                "runtime_clock_owns_missed_run_time",
                "late_within_grace_preserves_dispatch_eligibility",
                "expired_command_emits_missed_run_receipt",
                "duplicate_dispatched_run_requires_terminal_receipt",
                "recovery_due_requires_review_actions",
                "tenant_command_action_scope_checked",
                "high_risk_source_receipts_bound",
                "temporal_missed_run_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_missed_run_time": [
                    "expired_command_emits_missed_run_receipt",
                ],
                "late_within_grace_preserves_dispatch_eligibility": [
                    "late_within_grace_remains_dispatch_eligible",
                ],
                "expired_command_emits_missed_run_receipt": [
                    "expired_command_emits_missed_run_receipt",
                ],
                "duplicate_dispatched_run_requires_terminal_receipt": [
                    "duplicate_dispatched_run_requires_terminal_receipt",
                ],
                "recovery_due_requires_review_actions": [
                    "recovery_due_when_late_but_not_expired",
                ],
                "tenant_command_action_scope_checked": [
                    "high_risk_missed_run_blocks_without_required_sources_and_evidence",
                    "optional_policy_still_blocks_on_tenant_mismatch",
                ],
                "high_risk_source_receipts_bound": [
                    "high_risk_missed_run_blocks_without_required_sources_and_evidence",
                ],
                "temporal_missed_run_receipt_schema_valid": [
                    "expired_command_emits_missed_run_receipt",
                ],
                "receipt_not_terminal_closure": [
                    "expired_command_emits_missed_run_receipt",
                ],
            },
        ),
        _surface(
            "temporal_recurrence_window",
            [
                "evaluate_temporal_recurrence_window",
                "RecurrenceWindowRequest",
                "TemporalRecurrenceWindowReceipt",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/temporal_recurrence_window.py",
                "schemas/temporal_recurrence_window_receipt.schema.json",
                "tests/test_gateway/test_temporal_recurrence_window.py",
            ],
            "Temporal recurrence-window receipts certify next recurring occurrences with runtime-owned time truth, tenant timezone preservation, DST-safe next-occurrence checks, recurrence completion, duplicate-run prevention, scheduler source receipts, evidence refs, and high-risk due-candidate reapproval binding before recurring dispatch.",
            [
                "runtime_clock_owns_recurrence_window_time",
                "tenant_timezone_preserved_across_dst",
                "candidate_must_match_next_occurrence",
                "future_candidate_defers_dispatch",
                "completed_series_blocks_dispatch",
                "duplicate_candidate_requires_terminal_receipt",
                "monthly_end_of_month_clamped",
                "high_risk_due_candidate_requires_reapproval_source",
                "temporal_recurrence_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
            runtime_witness_anchor_aliases={
                "runtime_clock_owns_recurrence_window_time": [
                    "daily_recurrence_preserves_local_time_across_dst_start",
                ],
                "tenant_timezone_preserved_across_dst": [
                    "daily_recurrence_preserves_local_time_across_dst_start",
                ],
                "candidate_must_match_next_occurrence": [
                    "daily_recurrence_preserves_local_time_across_dst_start",
                    "mismatched_candidate_blocks_dispatch",
                ],
                "future_candidate_defers_dispatch": [
                    "weekly_candidate_not_due_before_runtime_now",
                ],
                "completed_series_blocks_dispatch": [
                    "count_completed_does_not_create_next_occurrence",
                ],
                "duplicate_candidate_requires_terminal_receipt": [
                    "duplicate_candidate_requires_terminal_receipt",
                ],
                "monthly_end_of_month_clamped": [
                    "monthly_recurrence_clamps_end_of_month",
                ],
                "high_risk_due_candidate_requires_reapproval_source": [
                    "high_risk_due_candidate_requires_reapproval_source",
                ],
                "temporal_recurrence_window_receipt_schema_valid": [
                    "daily_recurrence_preserves_local_time_across_dst_start",
                ],
                "receipt_not_terminal_closure": [
                    "daily_recurrence_preserves_local_time_across_dst_start",
                ],
            },
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
            runtime_witness_anchor_aliases={
                "usable_memory_does_not_create_refresh_task": [
                    "refresh_not_required_for_usable_memory_schema_receipt",
                ],
                "stale_memory_creates_bounded_refresh_task": [
                    "stale_memory_creates_bounded_refresh_task",
                ],
                "evidence_type_coverage_gates_review_readiness": [
                    "complete_refresh_evidence_is_ready_for_review",
                ],
                "invalid_refresh_policy_blocks_task_creation": [
                    "refresh_planning_blocks_invalid_policy_and_scope",
                ],
                "superseded_memory_blocks_reactivation": [
                    "superseded_memory_does_not_create_refresh_task",
                ],
                "temporal_memory_refresh_receipt_schema_valid": [
                    "refresh_not_required_for_usable_memory_schema_receipt",
                ],
                "receipt_not_terminal_closure": [
                    "refresh_not_required_for_usable_memory_schema_receipt",
                ],
            },
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
            runtime_witness_anchor_aliases={
                "scheduled_command_requires_execute_at": [
                    "scheduler_blocks_missing_execute_at_idempotency_and_recurrence_rule"
                ],
                "idempotency_required": [
                    "scheduler_blocks_missing_execute_at_idempotency_and_recurrence_rule"
                ],
                "lease_acquired_before_dispatch": [
                    "scheduler_due_command_acquires_schema_valid_lease"
                ],
                "future_schedule_defers": [
                    "scheduler_future_command_defers_without_lease"
                ],
                "missed_run_receipt_emitted": [
                    "scheduler_expired_command_emits_missed_run_receipt"
                ],
                "retry_window_checked": [
                    "scheduler_retry_waits_until_retry_after_window"
                ],
                "high_risk_reapproval_required": [
                    "scheduler_blocks_high_risk_missing_recheck_evidence"
                ],
                "active_lease_blocks_duplicate_execution": [
                    "scheduler_blocks_existing_active_lease"
                ],
                "temporal_scheduler_receipt_schema_valid": [
                    "scheduler_due_command_acquires_schema_valid_lease"
                ],
                "receipt_not_terminal_closure": [
                    "scheduler_due_command_acquires_schema_valid_lease"
                ],
            },
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
            runtime_witness_anchor_aliases={
                "bounded_policy_cases_required": [
                    "policy_prover_rejects_empty_inputs",
                ],
                "empty_invariants_rejected": [
                    "policy_prover_rejects_empty_inputs",
                ],
                "counterexamples_are_concrete": [
                    "policy_prover_reports_counterexamples_for_missing_or_mismatched_fields",
                    "payment_requires_approval_counterexample",
                    "tenant_isolation_counterexample",
                    "shell_requires_sandbox_counterexample",
                    "provider_url_approved_counterexample",
                    "memory_requires_admission_counterexample",
                    "unknown_property_fails_closed",
                ],
                "proved_report_has_no_counterexamples": [
                    "policy_prover_emits_proved_report_for_passing_cases",
                ],
                "policy_weakening_forbidden": [
                    "policy_proof_report_schema_contract_is_bounded_and_non_weakening",
                ],
                "policy_proof_schema_valid": [
                    "policy_proof_report_schema_valid",
                ],
            },
        ),
        _surface(
            "autonomous_capability_upgrade",
            [
                "/runtime/self/capability-improvement-portfolio",
                "AutonomousCapabilityUpgradeLoop.propose",
                "AutonomousCapabilityUpgradeLoop.propose_portfolio",
                "CapabilityHealthSignal",
                "CapabilityUpgradePlan",
                "CapabilityImprovementPortfolio",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "gateway/autonomous_capability_upgrade.py",
                "schemas/capability_improvement_portfolio.schema.json",
                "schemas/capability_upgrade_plan.schema.json",
                "tests/test_gateway/test_autonomous_capability_upgrade.py",
                "tests/test_gateway/test_reflex_endpoints.py",
            ],
            "Autonomous capability upgrade converts health signals into activation-blocked single-capability proposals and whole-mesh portfolios through a guarded read-only endpoint that requires evals, sandbox tests, ChangeCommand, ChangeCertificate, canary, terminal closure, and learning admission before promotion.",
            [
                "health_signal_requires_evidence_refs",
                "upgrade_candidates_are_promotion_blocked",
                "capability_improvement_portfolios_are_activation_blocked",
                "capability_improvement_portfolio_endpoint_operator_guarded",
                "capability_improvement_portfolio_endpoint_read_only",
                "capability_improvement_portfolio_identity_sets_are_unique",
                "systemic_weaknesses_are_ranked",
                "critical_governance_changes_require_second_approval",
                "capability_upgrade_plan_schema_valid",
                "capability_improvement_portfolio_schema_valid",
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
            "Autonomous test generation converts matching certified failure traces into activation-blocked, operator-review-required replay, policy, tenant, approval, budget, and sandbox test proposals while rejecting unanchored empty plans.",
            [
                "failure_trace_requires_evidence_refs",
                "generation_requires_matching_certified_trace",
                "high_risk_failures_generate_governance_variants",
                "plans_are_activation_blocked",
                "schema_rejects_unanchored_empty_generation_plan",
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
            [
                "/api/v1/replay/{trace_id}/determinism",
                "/api/v1/replay/reports",
                "/api/v1/replay/reports/{replay_id}",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/replay_report_integration.py",
                "mcoi/mcoi_runtime/app/routers/replay.py",
                "mcoi/mcoi_runtime/core/replay_determinism_harness.py",
                "mcoi/mcoi_runtime/persistence/replay_report_store.py",
                "mcoi/tests/test_replay_determinism_endpoints.py",
                "mcoi/tests/test_replay_determinism_harness.py",
                "mcoi/tests/test_replay_report_store.py",
                "docs/03_trace_and_replay.md",
            ],
            "Replay determinism routes emit governed reports over completed traces with bounded operation specs, persist report history through env-governed storage, and expose bounded operator report-history read models.",
            [
                "replay_determinism_endpoint_returns_match_report",
                "replay_determinism_endpoint_persists_report_history",
                "replay_determinism_endpoint_reports_unknown_operation",
                "replay_determinism_endpoint_missing_trace_fails_closed",
                "replay_report_history_missing_id_fails_closed",
                "harness_reports_deterministic_match",
                "harness_report_hash_is_deterministic",
                "harness_reports_sequence_gap_before_replay",
                "harness_reports_operation_errors_bounded",
                "replay_report_store_appends_lists_and_gets_reports",
                "replay_report_store_rejects_id_collision",
                "file_replay_report_store_persists_and_reloads",
                "file_replay_report_store_rejects_tampered_hash",
                "replay_report_store_path_validation_requires_absolute_json_path",
                "replay_report_store_integration_selects_memory_or_file",
            ],
        ),
        _surface(
            "tool_invocation",
            ["/api/v1/tools/invoke", "/api/v1/workflow/tools"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/data/tools.py",
                "mcoi/mcoi_runtime/app/routers/workflow.py",
                "mcoi/mcoi_runtime/core/governed_tool_gateway.py",
                "mcoi/mcoi_runtime/core/governed_tool_use.py",
                "mcoi/mcoi_runtime/core/tool_use.py",
                "mcoi/mcoi_runtime/governance/audit/rejected_path_records.py",
                "mcoi/mcoi_runtime/mcp/capability_bridge.py",
                "gateway/mcp_operator_read_model.py",
                "gateway/mcp_capability_fabric.py",
                "gateway/mcp_capabilities.py",
                "scripts/validate_mcp_capability_manifest.py",
                "scripts/validate_mcp_operator_checklist.py",
                "examples/mcp_capability_manifest.json",
                "examples/mcp_operator_handoff_checklist.json",
                "docs/55_mcp_capability_manifest.md",
                "mcoi/tests/test_governed_tool_gateway.py",
                "mcoi/tests/test_governed_tool_use.py",
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_server_phase213.py",
                "mcoi/tests/test_server_runtime_helpers.py",
                "tests/test_gateway/test_mcp_capability_fabric.py",
                "tests/test_validate_mcp_capability_manifest.py",
                "tests/test_validate_mcp_operator_checklist.py",
            ],
            "Tool invocation and MCP capability import bind action proof ids, capability policy receipts, rejected-path receipts, authority-obligation ownership records, validated operator manifests, and machine-readable handoff checklists.",
            [
                "invoke_tool",
                "invoke_tool_rejects_unsafe_expression",
                "invoke_unknown_tool",
                "tool_history",
                "tool_workflow",
                "tool_workflow_tool_calls_include_policy_receipts",
                "gateway_records_denied_tool_in_rejected_path_recorder",
                "blocked_tool_decision_records_rejected_path_receipt",
                "rejected_path_recorder_can_be_bound_after_registry_creation",
                "register_default_tools_registers_calculator_and_time",
                "validate_mcp_capability_manifest_accepts_example",
                "validate_mcp_operator_checklist_accepts_example",
            ],
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
            [
                "query_generates_proof",
                "execute_generates_proof",
                "query_returns_request_envelope_proof",
                "execute_returns_request_envelope_proof",
                "llm_result_metadata_has_request_envelope_proof",
                "query_proof_failure_is_audited_and_blocks_operation",
                "execute_proof_failure_blocks_dispatch",
                "llm_proof_failure_blocks_llm_bridge",
            ],
        ),
        _surface(
            "health_docs_exempt",
            ["/health", "/docs", "/openapi.json", "/redoc"],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
            ["gateway/server.py", "tests/test_gateway/test_webhooks.py"],
            "Operational liveness and documentation surfaces are outside the proof-critical path.",
            [
                "health",
            ],
        ),
        _surface(
            "lineage_query_api",
            [
                "/api/v1/lineage/resolve",
                "/api/v1/lineage/{trace_id}",
                "/api/v1/lineage/output/{output_id}",
                "/api/v1/lineage/command/{command_id}",
                "/api/v1/lineage/artifact/{artifact_id}",
            ],
            "read_model",
            "read_model",
            "read_model",
            "proven",
            [
                "mcoi/mcoi_runtime/app/routers/lineage.py",
                "mcoi/mcoi_runtime/core/lineage_query.py",
                "mcoi/tests/test_server_lineage.py",
                "docs/42_lineage_query_api.md",
                "schemas/lineage_query.schema.json",
                "schemas/trace_entry.schema.json",
                "schemas/replay_record.schema.json",
            ],
            "Lineage query API resolves read-only lineage:// URIs with bounded output, command, artifact, graph, policy-version, and policy-registry metadata read models.",
            [
                "lineage_resolve_route_returns_trace_document",
                "lineage_trace_permalink_route_returns_document",
                "lineage_route_enriches_policy_registry_metadata",
                "lineage_output_permalink_returns_unresolved_document",
                "lineage_output_permalink_resolves_indexed_trace",
                "lineage_command_permalink_resolves_indexed_trace",
                "lineage_artifact_permalink_resolves_persisted_dag",
                "lineage_resolve_rejects_invalid_uri",
            ],
        ),
        _surface(
            "god_mode_lifecycle",
            [
                "/api/v1/god-mode/capabilities",
                "/api/v1/god-mode/health",
                "/api/v1/god-mode/modules",
                "/api/v1/god-mode/capabilities/{module}/{name}",
                "/api/v1/god-mode/capabilities/{module}/{name}/agree-to-register",
                "/api/v1/god-mode/agreements/{agreement_id}/withdraw",
                "/api/v1/god-mode/capabilities/{module}/{name}/suspend",
                "/api/v1/god-mode/capabilities/{module}/{name}/resume",
                "/api/v1/god-mode/capabilities/{module}/{name}/issue-ticket",
                "/api/v1/god-mode/tickets",
                "/api/v1/god-mode/tickets/{ticket_id}",
                "/api/v1/god-mode/tickets/{ticket_id}/consume",
                "/api/v1/god-mode/tickets/{ticket_id}/revoke",
                "/api/v1/god-mode/receipts",
            ],
            "action_proof",
            "action_proof",
            "audit_chain",
            "proven",
            [
                "mcoi/mcoi_runtime/contracts/god_mode.py",
                "mcoi/mcoi_runtime/core/god_mode_registry.py",
                "mcoi/mcoi_runtime/core/god_mode_engine.py",
                "mcoi/mcoi_runtime/core/god_mode_integration.py",
                "mcoi/mcoi_runtime/core/god_mode_demonstrators.py",
                "mcoi/mcoi_runtime/app/routers/god_mode.py",
                "mcoi/tests/test_god_mode_contracts.py",
                "mcoi/tests/test_god_mode_registry.py",
                "mcoi/tests/test_god_mode_engine.py",
                "mcoi/tests/test_god_mode_dual_control.py",
                "mcoi/tests/test_god_mode_invariants.py",
                "mcoi/tests/test_god_mode_hardening.py",
                "mcoi/tests/test_god_mode_router.py",
                "mcoi/tests/test_god_mode_decorator.py",
            ],
            (
                "Privileged 'god mode' capabilities ship dormant. Two-stage explicit consent - "
                "registration agreement promotes capability dormant-to-armed; activation issues "
                "a single-use, short-lived ticket. Catastrophic capabilities require dual "
                "control (at least 2 distinct approvers). Every consumption emits an immutable "
                "receipt with pre/post hashes and the full agreement chain. Withdrawals and "
                "revocations are first-class, irreversible-as-events."
            ),
            [
                "capability_keys_are_unique",
                "every_capability_declares_at_least_one_bypass",
                "catastrophic_caps_require_dual_control",
                "catastrophic_caps_are_one_shot",
                "catastrophic_caps_have_short_ttl",
                "secrets_capabilities_use_strictest_floor",
                "agree_to_register_arms_capability",
                "issue_ticket_requires_armed",
                "double_consume_rejected",
                "consume_ticket_emits_receipt",
                "revoke_ticket_blocks_consume",
                "withdraw_agreement_reverts_state",
                "two_distinct_agreements_arm_capability",
                "end_to_end_consent_chain",
            ],
        ),
        _surface(
            "snet_operator_read_model",
            [
                "/api/v1/snet/operator/read-model",
                "build_snet_operator_read_model",
                "scripts.validate_snet_operator_read_model.validate_contract",
                "scripts.validate_snet_operator_read_model.validate_read_model",
                "examples/snet_operator_read_model.json",
                "docs/73_snet_operator_read_model.md",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "docs/73_snet_operator_read_model.md",
                "docs/START_HERE.md",
                "mcoi/mcoi_runtime/contracts/snet.py",
                "mcoi/mcoi_runtime/app/routers/snet.py",
                "mcoi/mcoi_runtime/snet/engine.py",
                "mcoi/mcoi_runtime/snet/read_model.py",
                "schemas/snet_operator_read_model.schema.json",
                "schemas/snet_mesh_receipt.schema.json",
                "scripts/validate_snet_operator_read_model.py",
                "scripts/validate_snet_mesh_receipt.py",
                "examples/snet_operator_read_model.json",
                "tests/test_validate_snet_operator_read_model.py",
                "tests/test_validate_snet_mesh_receipt.py",
                "tests/test_snet_operator_read_model_doc.py",
                "mcoi/tests/test_snet_router.py",
            ],
            (
                "SNet operator read model projects bounded symbol summaries through "
                "a read-only MCOI route, mesh receipt counts, settlement counts, "
                "raw-answer suppression, raw-metadata suppression, and denied "
                "execution, connector, filesystem, gateway, mutation, and "
                "terminal-closure authority."
            ),
            [
                "snet_operator_read_model_exposes_bounded_no_authority_projection",
                "snet_operator_read_model_zero_symbol_projection_is_valid",
                "snet_operator_read_model_rejects_invalid_bound_without_server_error",
                "snet_operator_read_model_has_no_mutation_companion",
                "default_router_mounts_snet_operator_read_model",
                "snet_operator_read_model_contract_passes",
                "snet_operator_read_model_rejects_raw_and_authority_mutations",
                "snet_operator_read_model_saved_file_validation",
                "snet_operator_read_model_rejects_count_drift",
                "snet_operator_read_model_rejects_symbol_raw_field",
                "snet_operator_read_model_zero_symbol_projection_is_valid",
                "snet_operator_read_model_malformed_root_reports_errors",
                "snet_operator_read_model_non_integer_truncation_reports_errors",
                "snet_mesh_receipt_contract_passes",
                "snet_mesh_receipt_rejects_raw_answer_and_authority_mutations",
                "snet_mesh_receipt_saved_file_validation",
                "snet_mesh_receipt_rejects_settlement_count_drift",
                "snet_mesh_receipt_requires_digest_evidence_ref",
                "snet_mesh_receipt_non_string_evidence_ref_reports_errors",
                "snet_mesh_receipt_malformed_payload_reports_errors",
                "snet_mesh_receipt_rejects_identity_drift",
                "snet_operator_doc_declares_read_only_boundary",
                "snet_operator_doc_names_blocked_authorities",
                "snet_operator_doc_lists_verification_commands",
                "start_here_links_snet_operator_doc",
            ],
        ),
        _surface(
            "agentic_service_harness_read_models",
            [
                "scripts.validate_agentic_service_harness_read_model_binding_plan.validate_read_model_binding_plan",
                "scripts.validate_agentic_service_harness_read_models.validate_agentic_service_harness_read_models",
                "scripts.validate_agentic_service_harness_read_model_projections.project_contract_to_read_model",
                "scripts.validate_agentic_service_harness_read_model_projections.validate_agentic_service_harness_read_model_projections",
                "scripts.validate_agentic_service_harness_read_model_integrity.validate_agentic_service_harness_read_model_integrity",
                "examples/agentic_service_harness_read_models.foundation.json",
                "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md",
                "examples/agentic_service_harness_read_models.foundation.json",
                "schemas/agentic_service_harness.schema.json",
                "schemas/agentic_service_harness_read_models.schema.json",
                "scripts/validate_agentic_service_harness_contract.py",
                "scripts/validate_agentic_service_harness_read_model_binding_plan.py",
                "scripts/validate_agentic_service_harness_read_models.py",
                "scripts/validate_agentic_service_harness_read_model_projections.py",
                "scripts/validate_agentic_service_harness_read_model_integrity.py",
                "tests/test_validate_agentic_service_harness_read_model_binding_plan.py",
                "tests/test_validate_agentic_service_harness_read_models.py",
                "tests/test_validate_agentic_service_harness_read_model_projections.py",
                "tests/test_validate_agentic_service_harness_read_model_integrity.py",
            ],
            (
                "Agentic Service Harness read models remain planning-only, "
                "read-only, reference-consistent, redacted, non-terminal, and "
                "projection-bound to source contract fixtures before UI, "
                "mutation endpoints, external adapters, branch writes, pull "
                "requests, or high-risk authority are admitted."
            ),
            [
                "harness_read_model_binding_plan_is_planning_only",
                "harness_read_model_schema_accepts_default_example",
                "harness_read_model_rejects_mutation_and_secret_surfaces",
                "harness_read_model_rejects_missing_identity_refs",
                "harness_read_model_blocks_terminal_closure_claims",
                "harness_read_model_projection_covers_contract_scenarios",
                "harness_read_model_projection_preserves_core_refs",
                "harness_read_model_projection_rejects_source_authority",
                "harness_read_model_projection_rejects_source_mutation_routes",
                "harness_read_model_integrity_preserves_identity_mesh",
                "harness_read_model_integrity_rejects_identity_drift",
                "harness_read_model_validators_emit_strict_receipts",
            ],
            runtime_witness_anchor_aliases={
                "harness_read_model_binding_plan_is_planning_only": [
                    "read_model_binding_plan_accepts_default_artifact",
                    "read_model_binding_plan_rejects_missing_required_symbol",
                    "read_model_binding_plan_rejects_mutation_route_string",
                ],
                "harness_read_model_schema_accepts_default_example": [
                    "agentic_service_harness_read_models_accept_default_example",
                ],
                "harness_read_model_rejects_mutation_and_secret_surfaces": [
                    "agentic_service_harness_read_models_reject_mutation_flag",
                    "agentic_service_harness_read_models_reject_mutation_route_string",
                    "agentic_service_harness_read_models_reject_secret_like_payload",
                ],
                "harness_read_model_rejects_missing_identity_refs": [
                    "agentic_service_harness_read_models_reject_missing_run_ref",
                ],
                "harness_read_model_blocks_terminal_closure_claims": [
                    "agentic_service_harness_read_models_reject_terminal_closure_claim",
                    "read_model_projection_detects_terminal_projection_claim",
                ],
                "harness_read_model_projection_covers_contract_scenarios": [
                    "read_model_projections_accept_all_default_contract_fixtures",
                ],
                "harness_read_model_projection_preserves_core_refs": [
                    "projected_read_only_contract_preserves_core_refs",
                ],
                "harness_read_model_projection_rejects_source_authority": [
                    "read_model_projection_rejects_source_write_authority",
                ],
                "harness_read_model_projection_rejects_source_mutation_routes": [
                    "read_model_projection_rejects_source_mutation_route_string",
                ],
                "harness_read_model_integrity_preserves_identity_mesh": [
                    "read_model_integrity_accepts_default_contract_fixtures",
                ],
                "harness_read_model_integrity_rejects_identity_drift": [
                    "read_model_integrity_rejects_run_receipt_drift",
                    "read_model_integrity_rejects_project_run_ref_drift",
                    "read_model_integrity_rejects_receipt_evidence_drift",
                    "read_model_integrity_rejects_duplicate_projected_run_ids",
                ],
                "harness_read_model_validators_emit_strict_receipts": [
                    "agentic_service_harness_read_models_writer_and_cli_honor_strict",
                    "read_model_projection_writer_and_cli_honor_strict",
                    "read_model_integrity_writer_and_cli_honor_strict",
                    "read_model_binding_plan_cli_json_reports_valid",
                ],
            },
        ),
        _surface(
            "agentic_service_harness_authority_transitions",
            [
                "scripts.validate_agentic_service_harness_contract.validate_agentic_service_harness_contract",
                "scripts.validate_agentic_service_harness_authority_transitions.validate_agentic_service_harness_authority_transitions",
                "examples/agentic_service_harness.read_only.json",
                "examples/agentic_service_harness.dry_run.json",
                "examples/agentic_service_harness.branch_write_awaiting_approval.json",
                "examples/agentic_service_harness.open_pr_awaiting_approval.json",
                "examples/agentic_service_harness.blocked_high_risk.json",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/agentic_service_harness.schema.json",
                "scripts/validate_agentic_service_harness_contract.py",
                "scripts/validate_agentic_service_harness_authority_transitions.py",
                "examples/agentic_service_harness.read_only.json",
                "examples/agentic_service_harness.dry_run.json",
                "examples/agentic_service_harness.branch_write_awaiting_approval.json",
                "examples/agentic_service_harness.open_pr_awaiting_approval.json",
                "examples/agentic_service_harness.blocked_high_risk.json",
                "tests/test_gateway/test_agentic_service_harness_contract.py",
                "tests/test_validate_agentic_service_harness_authority_transitions.py",
            ],
            (
                "Agentic Service Harness authority transitions keep read-only "
                "and dry-run scenarios non-effectful, branch-write and open-PR "
                "scenarios approval-pending, and high-risk merge, deploy, DNS, "
                "secret, and destructive actions blocked by default before UI "
                "or external execution authority is admitted."
            ),
            [
                "harness_authority_transitions_accept_default_fixtures",
                "harness_authority_rejects_approved_branch_gate",
                "harness_authority_rejects_dry_run_file_change",
                "harness_authority_rejects_open_pr_without_branch_evidence",
                "harness_authority_rejects_incomplete_high_risk_block",
                "harness_authority_validator_emits_strict_receipt",
            ],
            runtime_witness_anchor_aliases={
                "harness_authority_transitions_accept_default_fixtures": [
                    "authority_transitions_accept_default_contract_fixtures",
                ],
                "harness_authority_rejects_approved_branch_gate": [
                    "authority_transition_rejects_approved_branch_gate",
                ],
                "harness_authority_rejects_dry_run_file_change": [
                    "authority_transition_rejects_dry_run_file_change",
                ],
                "harness_authority_rejects_open_pr_without_branch_evidence": [
                    "authority_transition_rejects_open_pr_without_branch_evidence",
                ],
                "harness_authority_rejects_incomplete_high_risk_block": [
                    "authority_transition_rejects_incomplete_high_risk_block",
                ],
                "harness_authority_validator_emits_strict_receipt": [
                    "authority_transition_writer_and_cli_honor_strict",
                ],
            },
        ),
        _surface(
            "snet_episode_replay",
            [
                "scripts.validate_snet_episode_replay.validate_contract",
                "scripts.validate_snet_episode_replay.validate_episode",
                "scripts.validate_snet_episode_replay.replay_episode",
                "examples/snet_episode_seed_dependency.json",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "schemas/snet_episode.schema.json",
                "schemas/snet_mesh_receipt.schema.json",
                "scripts/validate_snet_episode_replay.py",
                "scripts/validate_snet_mesh_receipt.py",
                "examples/snet_episode_seed_dependency.json",
                "tests/test_validate_snet_episode_replay.py",
            ],
            (
                "SNet episode replay binds a bounded seed symbol, WH answer "
                "bindings, deterministic input digest, expected mesh receipt, "
                "raw-answer exposure denial, authority denial, and saved "
                "example replay into one local proof surface. Replay produces "
                "read-only SNet mesh evidence and is not terminal closure."
            ),
            [
                "snet_episode_replay_contract_passes",
                "snet_episode_replay_is_deterministic",
                "snet_episode_rejects_answer_drift",
                "snet_episode_rejects_authority_and_raw_field_mutations",
                "snet_episode_rejects_expected_count_drift",
                "snet_episode_malformed_answer_bindings_report_errors",
                "snet_episode_non_json_replay_inputs_report_errors",
                "snet_episode_malformed_expected_receipt_report_errors",
                "snet_episode_malformed_root_reports_errors",
                "snet_episode_saved_file_validation",
                "committed_snet_episode_example_replays_to_expected_receipt",
            ],
        ),
        _surface(
            "operational_math_loop",
            [
                "/api/v1/dashboard/operational-math",
                "OperationalMathLoopEngine.apply_all",
                "mcoi_runtime.app.operational_math_cli",
                "mcoi_runtime.app.operational_math_observability",
                "OperationalMathReceiptStore",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/operational_math_loop.md",
                "mcoi/mcoi_runtime/contracts/operational_math.py",
                "mcoi/mcoi_runtime/core/operational_math_loop.py",
                "mcoi/mcoi_runtime/persistence/operational_math_receipt_store.py",
                "mcoi/mcoi_runtime/app/operational_math_cli.py",
                "mcoi/mcoi_runtime/app/operational_math_observability.py",
                "mcoi/mcoi_runtime/app/routers/ops/summaries.py",
                "mcoi/mcoi_runtime/app/server.py",
                "mcoi/tests/test_operational_math_loop.py",
                "mcoi/tests/test_operational_math_cli.py",
                "mcoi/tests/test_operational_math_receipt_store.py",
                "mcoi/tests/test_operational_math_observability.py",
                "mcoi/tests/test_operational_math_dashboard_router.py",
            ],
            (
                "Operational math converts the F1-F10 audit into bounded roles, "
                "controls, proof references, event-spine records, append-only JSON "
                "receipt stores, and dashboard-safe operator review projections "
                "without silent completion when unresolved principles remain."
            ),
            [
                "operational_math_loop_applies_all_audit_principles",
                "operational_math_loop_stops_at_iteration_budget_with_open_gaps",
                "operational_math_loop_blocks_solvedverified_without_control_binding",
                "operational_math_loop_blocks_solvedverified_with_failed_control_binding",
                "operational_math_cli_emits_saturated_receipt",
                "operational_math_cli_reports_bounded_incomplete_receipt",
                "operational_math_cli_writes_dashboard_projection",
                "operational_math_cli_appends_receipt_store",
                "memory_store_appends_queries_and_summarizes_receipts",
                "memory_store_surfaces_unverified_control_review_reason",
                "file_store_persists_and_reloads_receipts",
                "summary_marks_incomplete_receipt_for_review",
                "summary_marks_unverified_controls_for_review",
                "registers_operational_math_observability_source",
                "registers_operational_math_store_observability_source",
                "server_wires_operational_math_store_into_dashboard",
            ],
        ),
        _surface(
            "holistic_loop_read_model_kernel",
            [
                "/api/v1/loops/read-model",
                "LoopRegistry",
                "LoopReadModel",
                "LoopStatusBinding",
                "LoopTransitionBinding",
                "LoopModeBinding",
                "LoopReceiptLineageBinding",
                "LoopClosureConditionBinding",
                "LoopClosureEvidencePack",
                "LoopOperatorClosureReadinessView",
                "LoopProofObligationView",
                "LoopAuditEvolutionView",
                "LoopRecoveryReadinessView",
                "LoopAuthorityBinding",
                "LoopRiskBinding",
                "LoopRollbackBinding",
                "LoopLearningBinding",
                "LoopStepReceipt",
                "LoopClosureReport",
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "docs/HOLISTIC_LOOP_ENGINEERING_KERNEL.md",
                "docs/HOLISTIC_LOOP_ENGINEERING_KERNEL_PR_PACKET.md",
                "mcoi/mcoi_runtime/contracts/holistic_loop.py",
                "mcoi/mcoi_runtime/core/holistic_loop_registry.py",
                "mcoi/mcoi_runtime/app/routers/loops.py",
                "schemas/holistic_loop_read_model.schema.json",
                "tests/fixtures/holistic_loop_read_model_v1_golden.json",
                "scripts/report_holistic_loop_candidate_map.py",
                "scripts/report_holistic_loop_admission_closure.py",
                "scripts/report_holistic_loop_uao_admission_dossier.py",
                "scripts/report_holistic_loop_workflow_admission_dossier.py",
                "scripts/report_holistic_loop_authority_admission_dossier.py",
                "scripts/report_holistic_loop_audit_proof_admission_dossier.py",
                "scripts/report_holistic_loop_governed_symbolic_admission_dossier.py",
                "scripts/report_holistic_loop_read_model.py",
                "scripts/validate_holistic_loop_extension_admission.py",
                "scripts/validate_holistic_loop_kernel_freeze.py",
                "scripts/validate_holistic_loop_read_model.py",
                "scripts/validate_holistic_loop_http_surface.py",
                "mcoi/tests/test_holistic_loop_kernel.py",
                "mcoi/tests/test_holistic_loop_router.py",
                "tests/test_report_holistic_loop_candidate_map.py",
                "tests/test_report_holistic_loop_admission_closure.py",
                "tests/test_report_holistic_loop_uao_admission_dossier.py",
                "tests/test_report_holistic_loop_workflow_admission_dossier.py",
                "tests/test_report_holistic_loop_authority_admission_dossier.py",
                "tests/test_report_holistic_loop_audit_proof_admission_dossier.py",
                "tests/test_report_holistic_loop_governed_symbolic_admission_dossier.py",
                "tests/test_report_holistic_loop_read_model.py",
                "tests/test_validate_holistic_loop_extension_admission.py",
                "tests/test_validate_holistic_loop_kernel_freeze.py",
                "tests/test_validate_holistic_loop_read_model.py",
                "tests/test_validate_holistic_loop_http_surface.py",
            ],
            (
                "Holistic loop engineering exposes existing governed loops through "
                "one read-only loop contract, registry, schema-backed summary, "
                "status catalog, transition catalog, mode catalog, closure "
                "condition catalog, authority catalog, risk catalog, rollback "
                "catalog, learning catalog, bounded receipt trail, receipt "
                "lineage catalog, closure evidence pack, operator closure "
                "readiness view, proof obligation view, audit evolution "
                "view, recovery readiness view, and HTTP "
                "read model. The v1 freeze validator pins a golden snapshot, "
                "schema/report/HTTP parity, additive-only extension policy, "
                "zero-unanchored proof-label guard, and extension admission "
                "guard for default registry additions. The candidate map lists "
                "candidate loop surfaces and reports their current registry "
                "admission state. "
                "The UAO loop is registered in the default read model as a "
                "read-only blocked loop, and its admission dossier reports "
                "registry admission without causing mutation. "
                "The workflow loop is registered in the default read model as a "
                "read-only blocked loop, and its admission dossier reports "
                "registry admission without causing mutation. "
                "The authority loop is registered in the default read model "
                "as a read-only blocked loop, and its admission dossier reports "
                "registry admission without causing mutation. "
                "The audit/proof loop is registered in the default read model "
                "as a read-only blocked loop, and its admission dossier reports "
                "registry admission without causing mutation. "
                "The governed symbolic loop is registered in the default read "
                "model as a read-only blocked loop with no real mode, and its "
                "admission dossier reports registry admission without causing "
                "mutation. "
                "The admission closure report proves all tracked candidate "
                "surfaces are admitted, no candidate admission remains pending, "
                "extension admission is valid, and holistic proof labels remain "
                "anchored while still requiring terminal closure. "
                "Missing authority or "
                "evidence remains an explicit blocker and no mutation route is "
                "introduced."
            ),
            [
                "registered_loops_expose_governed_manifest_fields",
                "missing_required_evidence_is_reported_as_blocker",
                "closure_report_blocks_incomplete_evidence",
                "loop_registry_rejects_duplicate_loop_ids",
                "loop_status_bindings_explain_projected_status",
                "loop_transition_bindings_describe_allowed_transitions",
                "loop_mode_bindings_cover_allowed_modes",
                "loop_closure_condition_bindings_cover_conditions",
                "loop_closure_evidence_pack_aggregates_closure_inputs",
                "loop_operator_closure_readiness_view_summarizes_next_action",
                "loop_proof_obligation_view_groups_required_proof_inputs",
                "loop_audit_evolution_view_groups_receipts_blockers_and_learning_refs",
                "loop_recovery_readiness_view_groups_rollback_blockers_and_lineage_refs",
                "loop_authority_bindings_cover_required_authority",
                "loop_risk_bindings_cover_risk_class",
                "loop_rollback_bindings_cover_recovery_policy",
                "loop_learning_bindings_cover_learning_policy",
                "loop_evidence_bindings_cover_required_evidence",
                "loop_step_receipt_trail_is_read_only",
                "loop_receipt_lineage_bindings_cover_step_receipts",
                "loop_closure_report_blocks_terminal_closure",
                "loop_read_model_endpoint_is_read_only",
                "loop_http_surface_validator_rejects_mutation_routes",
                "loop_kernel_v1_golden_snapshot_matches_current_report",
                "loop_kernel_v1_report_schema_http_parity_holds",
                "loop_kernel_v1_extension_policy_is_documented",
                "holistic_loop_witness_integrity_has_zero_unanchored_labels",
                "holistic_loop_extension_admission_guards_default_registry",
                "holistic_loop_candidate_map_lists_candidate_surfaces",
                "holistic_loop_candidate_map_is_read_only_non_terminal",
                "holistic_loop_admission_closure_reports_no_pending_candidates",
                "holistic_loop_audit_proof_registered_in_default_read_model",
                "holistic_loop_authority_registered_in_default_read_model",
                "holistic_loop_uao_registered_in_default_read_model",
                "holistic_loop_workflow_registered_in_default_read_model",
                "holistic_loop_governed_symbolic_registered_in_default_read_model",
                "holistic_loop_uao_admission_dossier_builds_proposed_manifest",
                "holistic_loop_uao_admission_dossier_reports_registry_admission",
                "holistic_loop_uao_admission_dossier_blocks_registration_effects",
                "holistic_loop_workflow_admission_dossier_builds_proposed_manifest",
                "holistic_loop_workflow_admission_dossier_reports_registry_admission",
                "holistic_loop_workflow_admission_dossier_blocks_registration_effects",
                "holistic_loop_authority_admission_dossier_builds_proposed_manifest",
                "holistic_loop_authority_admission_dossier_reports_registry_admission",
                "holistic_loop_authority_admission_dossier_blocks_registration_effects",
                "holistic_loop_audit_proof_admission_dossier_builds_proposed_manifest",
                "holistic_loop_audit_proof_admission_dossier_reports_registry_admission",
                "holistic_loop_audit_proof_admission_dossier_blocks_registration_effects",
                "holistic_loop_governed_symbolic_admission_dossier_builds_proposed_manifest",
                "holistic_loop_governed_symbolic_admission_dossier_reports_registry_admission",
                "holistic_loop_governed_symbolic_admission_dossier_blocks_registration_effects",
            ],
            runtime_witness_anchor_aliases={
                "registered_loops_expose_governed_manifest_fields": [
                    "default_registry_exposes_governed_loop_manifests"
                ],
                "missing_required_evidence_is_reported_as_blocker": [
                    "missing_evidence_is_reported_as_blocker_not_success"
                ],
                "closure_report_blocks_incomplete_evidence": [
                    "loop_receipt_and_closure_report_contracts_are_explicit"
                ],
                "loop_registry_rejects_duplicate_loop_ids": [
                    "loop_registry_rejects_duplicate_loop_ids"
                ],
                "loop_status_bindings_explain_projected_status": [
                    "loop_status_bindings_explain_projected_status_without_execution"
                ],
                "loop_transition_bindings_describe_allowed_transitions": [
                    "loop_transition_bindings_describe_allowed_transitions_without_execution"
                ],
                "loop_receipt_lineage_bindings_cover_step_receipts": [
                    "loop_receipt_lineage_bindings_cover_step_receipts_without_emission"
                ],
                "loop_mode_bindings_cover_allowed_modes": [
                    "loop_mode_bindings_cover_allowed_modes_without_execution"
                ],
                "loop_closure_condition_bindings_cover_conditions": [
                    "loop_closure_condition_bindings_cover_conditions_without_execution"
                ],
                "loop_closure_evidence_pack_aggregates_closure_inputs": [
                    "loop_closure_evidence_pack_aggregates_required_closure_inputs"
                ],
                "loop_operator_closure_readiness_view_summarizes_next_action": [
                    "loop_operator_closure_readiness_view_summarizes_blockers_and_next_action"
                ],
                "loop_proof_obligation_view_groups_required_proof_inputs": [
                    "loop_proof_obligation_view_groups_required_proof_inputs"
                ],
                "loop_audit_evolution_view_groups_receipts_blockers_and_learning_refs": [
                    "loop_audit_evolution_view_groups_receipts_blockers_and_learning_refs"
                ],
                "loop_recovery_readiness_view_groups_rollback_blockers_and_lineage_refs": [
                    "loop_recovery_readiness_view_groups_rollback_blockers_and_lineage_refs"
                ],
                "loop_authority_bindings_cover_required_authority": [
                    "loop_authority_bindings_cover_required_authority_without_execution"
                ],
                "loop_risk_bindings_cover_risk_class": [
                    "loop_risk_bindings_cover_risk_class_without_execution"
                ],
                "loop_rollback_bindings_cover_recovery_policy": [
                    "loop_rollback_bindings_cover_recovery_policy_without_execution"
                ],
                "loop_learning_bindings_cover_learning_policy": [
                    "loop_learning_bindings_cover_learning_policy_without_execution"
                ],
                "loop_evidence_bindings_cover_required_evidence": [
                    "loop_evidence_bindings_cover_required_evidence_without_execution"
                ],
                "loop_step_receipt_trail_is_read_only": [
                    "loop_summary_exposes_read_only_step_receipt_trail"
                ],
                "loop_closure_report_blocks_terminal_closure": [
                    "loop_summary_rejects_terminal_or_mismatched_closure_report"
                ],
                "loop_read_model_endpoint_is_read_only": [
                    "loop_read_model_has_no_mutation_companion"
                ],
                "loop_http_surface_validator_rejects_mutation_routes": [
                    "route_method_validation_rejects_mutation_route"
                ],
                "loop_kernel_v1_golden_snapshot_matches_current_report": [
                    "holistic_loop_kernel_freeze_contract_passes"
                ],
                "loop_kernel_v1_report_schema_http_parity_holds": [
                    "http_payload_normalizes_to_report_contract"
                ],
                "loop_kernel_v1_extension_policy_is_documented": [
                    "kernel_v1_policy_doc_contains_freeze_rules"
                ],
                "holistic_loop_witness_integrity_has_zero_unanchored_labels": [
                    "holistic_loop_witness_integrity_has_zero_unanchored_labels"
                ],
                "holistic_loop_extension_admission_guards_default_registry": [
                    "holistic_loop_extension_admission_guards_default_registry"
                ],
                "holistic_loop_candidate_map_lists_candidate_surfaces": [
                    "holistic_loop_candidate_map_lists_candidate_surfaces"
                ],
                "holistic_loop_candidate_map_is_read_only_non_terminal": [
                    "holistic_loop_candidate_map_is_read_only_non_terminal"
                ],
                "holistic_loop_admission_closure_reports_no_pending_candidates": [
                    "holistic_loop_admission_closure_reports_no_pending_candidates"
                ],
                "holistic_loop_audit_proof_registered_in_default_read_model": [
                    "audit_proof_loop_is_registered_read_only_and_blocked"
                ],
                "holistic_loop_authority_registered_in_default_read_model": [
                    "authority_obligation_loop_is_registered_read_only_and_blocked"
                ],
                "holistic_loop_uao_registered_in_default_read_model": [
                    "universal_action_orchestration_loop_is_registered_read_only_and_blocked"
                ],
                "holistic_loop_workflow_registered_in_default_read_model": [
                    "workflow_execution_loop_is_registered_read_only_and_blocked"
                ],
                "holistic_loop_governed_symbolic_registered_in_default_read_model": [
                    "governed_symbolic_loop_is_registered_read_only_and_blocked"
                ],
                "holistic_loop_uao_admission_dossier_builds_proposed_manifest": [
                    "uao_admission_dossier_builds_proposed_manifest"
                ],
                "holistic_loop_uao_admission_dossier_reports_registry_admission": [
                    "uao_admission_dossier_reports_registry_admission"
                ],
                "holistic_loop_uao_admission_dossier_blocks_registration_effects": [
                    "uao_admission_dossier_does_not_register_or_mutate_runtime"
                ],
                "holistic_loop_workflow_admission_dossier_builds_proposed_manifest": [
                    "workflow_admission_dossier_builds_proposed_manifest"
                ],
                "holistic_loop_workflow_admission_dossier_reports_registry_admission": [
                    "workflow_admission_dossier_reports_registry_admission"
                ],
                "holistic_loop_workflow_admission_dossier_blocks_registration_effects": [
                    "workflow_admission_dossier_does_not_register_or_mutate_runtime"
                ],
                "holistic_loop_authority_admission_dossier_builds_proposed_manifest": [
                    "authority_admission_dossier_builds_proposed_manifest"
                ],
                "holistic_loop_authority_admission_dossier_reports_registry_admission": [
                    "authority_admission_dossier_reports_registry_admission"
                ],
                "holistic_loop_authority_admission_dossier_blocks_registration_effects": [
                    "authority_admission_dossier_does_not_register_or_mutate_runtime"
                ],
                "holistic_loop_audit_proof_admission_dossier_builds_proposed_manifest": [
                    "audit_proof_admission_dossier_builds_proposed_manifest"
                ],
                "holistic_loop_audit_proof_admission_dossier_reports_registry_admission": [
                    "audit_proof_admission_dossier_reports_registry_admission"
                ],
                "holistic_loop_audit_proof_admission_dossier_blocks_registration_effects": [
                    "audit_proof_admission_dossier_does_not_register_or_mutate_runtime"
                ],
                "holistic_loop_governed_symbolic_admission_dossier_builds_proposed_manifest": [
                    "governed_symbolic_admission_dossier_builds_proposed_manifest"
                ],
                "holistic_loop_governed_symbolic_admission_dossier_reports_registry_admission": [
                    "governed_symbolic_admission_dossier_reports_registry_admission"
                ],
                "holistic_loop_governed_symbolic_admission_dossier_blocks_registration_effects": [
                    "governed_symbolic_admission_dossier_does_not_register_or_mutate_runtime"
                ],
            },
        ),
    ]
    closure_actions = [
        {
            "action_id": "bind_tool_arguments_to_capability_policy_receipts",
            "surfaces": ["tool_invocation", "gateway_capability_fabric"],
            "status": "closed",
        },
        {
            "action_id": "anchor_operational_math_loop_receipts_and_projection",
            "surfaces": ["operational_math_loop"],
            "status": "closed",
        },
        {
            "action_id": "publish_snet_episode_replay_contract",
            "surfaces": ["snet_episode_replay"],
            "status": "closed",
        },
        {
            "action_id": "publish_snet_operator_read_model_contract",
            "surfaces": ["snet_operator_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_agentic_service_harness_read_model_contract",
            "surfaces": ["agentic_service_harness_read_models"],
            "status": "closed",
        },
        {
            "action_id": "publish_agentic_service_harness_authority_transition_contract",
            "surfaces": ["agentic_service_harness_authority_transitions"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_harness_read_model",
            "surfaces": ["component_harness_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_operator_read_models",
            "surfaces": ["universal_symbol_operator_read_models"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_runtime_admission_policy",
            "surfaces": ["universal_symbol_runtime_admission_policy"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_runtime_admission_evidence_receipt",
            "surfaces": ["universal_symbol_runtime_admission_evidence_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_runtime_live_witness_input_receipt",
            "surfaces": ["universal_symbol_runtime_live_witness_input_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_repository_observation_evidence_packet",
            "surfaces": ["repository_observation_evidence_packet"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_lane_runtime_authority_evidence_receipt",
            "surfaces": ["universal_symbol_lane_runtime_authority_evidence_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_lane_runtime_authority_evidence_value_receipt",
            "surfaces": ["universal_symbol_lane_runtime_authority_evidence_value_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_runtime_authority_witness",
            "surfaces": ["universal_symbol_runtime_authority_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_runtime_authority_read_model",
            "surfaces": ["universal_symbol_runtime_authority_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_skill_runtime_authority_witness",
            "surfaces": ["universal_symbol_skill_runtime_authority_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_adapter_receipt_persistence_policy",
            "surfaces": ["universal_symbol_adapter_receipt_persistence_policy"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_operator_approval_witness",
            "surfaces": ["universal_symbol_receipt_store_operator_approval_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_operator_identity_witness",
            "surfaces": ["universal_symbol_receipt_store_operator_identity_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_operator_approval_decision_witness",
            "surfaces": ["universal_symbol_receipt_store_operator_approval_decision_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_operator_reapproval_expiry_witness",
            "surfaces": ["universal_symbol_receipt_store_operator_reapproval_expiry_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_operator_revocation_witness",
            "surfaces": ["universal_symbol_receipt_store_operator_revocation_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_reapproval_revocation_witness",
            "surfaces": ["universal_symbol_receipt_store_reapproval_revocation_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_lifecycle_evidence_receipt",
            "surfaces": ["universal_symbol_receipt_store_lifecycle_evidence_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_lifecycle_evidence_bundle",
            "surfaces": ["universal_symbol_receipt_store_lifecycle_evidence_bundle"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model",
            "surfaces": ["universal_symbol_receipt_store_lifecycle_evidence_bundle_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_lifecycle_audit_receipt",
            "surfaces": ["universal_symbol_receipt_store_lifecycle_audit_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_lifecycle_audit_read_model",
            "surfaces": ["universal_symbol_receipt_store_lifecycle_audit_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_replacement_decision_receipt",
            "surfaces": ["universal_symbol_receipt_store_replacement_decision_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_replacement_decision_read_model",
            "surfaces": ["universal_symbol_receipt_store_replacement_decision_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness",
            "surfaces": ["universal_symbol_receipt_store_replacement_decision_replay_idempotency_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model",
            "surfaces": ["universal_symbol_receipt_store_replacement_decision_replay_idempotency_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_tenant_scope_witness",
            "surfaces": ["universal_symbol_receipt_store_tenant_scope_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_tenant_scope_read_model",
            "surfaces": ["universal_symbol_receipt_store_tenant_scope_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_writer_duty_scope_witness",
            "surfaces": ["universal_symbol_receipt_store_writer_duty_scope_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_writer_duty_scope_read_model",
            "surfaces": ["universal_symbol_receipt_store_writer_duty_scope_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_path_confinement_witness",
            "surfaces": ["universal_symbol_receipt_store_path_confinement_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_path_confinement_read_model",
            "surfaces": ["universal_symbol_receipt_store_path_confinement_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_write_path_idempotency_witness",
            "surfaces": ["universal_symbol_receipt_store_write_path_idempotency_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_write_path_idempotency_read_model",
            "surfaces": ["universal_symbol_receipt_store_write_path_idempotency_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_durability_replay_witness",
            "surfaces": ["universal_symbol_receipt_store_durability_replay_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_durability_replay_read_model",
            "surfaces": ["universal_symbol_receipt_store_durability_replay_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_recovery_witness",
            "surfaces": ["universal_symbol_receipt_store_recovery_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_recovery_read_model",
            "surfaces": ["universal_symbol_receipt_store_recovery_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_writer_identity_witness",
            "surfaces": ["universal_symbol_receipt_store_writer_identity_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_writer_registration_witness",
            "surfaces": ["universal_symbol_receipt_store_writer_registration_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_path_custody_witness",
            "surfaces": ["universal_symbol_receipt_store_path_custody_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_write_path_witness",
            "surfaces": ["universal_symbol_receipt_store_write_path_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_receipt_store_authority_witness",
            "surfaces": ["universal_symbol_receipt_store_authority_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_universal_symbol_append_audit_witness",
            "surfaces": ["universal_symbol_append_audit_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_cross_channel_conversation_binding_policy",
            "surfaces": ["cross_channel_conversation_binding_policy"],
            "status": "closed",
        },
        {
            "action_id": "publish_policy_denial_response_composer",
            "surfaces": ["policy_denial_response_composer"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_autopsy",
            "surfaces": ["component_autopsy"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_request_simulator",
            "surfaces": ["component_request_simulator"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_bundle_compiler",
            "surfaces": ["component_bundle_compiler"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_ownership",
            "surfaces": ["component_route_family_ownership"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_preflight",
            "surfaces": ["component_route_family_promotion_preflight"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_witness_requirements",
            "surfaces": ["component_route_family_promotion_witness_requirements"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_witness_evidence",
            "surfaces": ["component_route_family_promotion_witness_evidence"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_approval_candidates",
            "surfaces": ["component_route_family_promotion_approval_candidates"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_approval_intake",
            "surfaces": ["component_route_family_promotion_approval_intake"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_submitted_evidence_verifier",
            "surfaces": ["component_route_family_promotion_submitted_evidence_verifier"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_submitted_evidence_records",
            "surfaces": ["component_route_family_promotion_submitted_evidence_records"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_submitted_evidence_payload_examples",
            "surfaces": ["component_route_family_promotion_submitted_evidence_payload_examples"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_operator_submitted_evidence_records",
            "surfaces": ["component_route_family_promotion_operator_submitted_evidence_records"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_gate_satisfaction_evaluator",
            "surfaces": ["component_route_family_promotion_gate_satisfaction_evaluator"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_authority_decision_report",
            "surfaces": ["component_route_family_promotion_authority_decision_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_route_binding_decision_report",
            "surfaces": ["component_route_family_promotion_route_binding_decision_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_lifecycle_transition_decision_report",
            "surfaces": ["component_route_family_promotion_lifecycle_transition_decision_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_authority_upgrade_witness_decision_report",
            "surfaces": ["component_route_family_promotion_authority_upgrade_witness_decision_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_product_ownership_decision_report",
            "surfaces": ["component_route_family_promotion_product_ownership_decision_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_terminal_closure_denial_report",
            "surfaces": ["component_route_family_promotion_terminal_closure_denial_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_missing_evidence_ledger",
            "surfaces": ["component_route_family_promotion_missing_evidence_ledger"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_candidate",
            "surfaces": ["component_route_family_promotion_router_inventory_delta_candidate"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_witness_requirements",
            "surfaces": ["component_route_family_promotion_router_inventory_delta_witness_requirements"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_witness_minting_preflight",
            "surfaces": ["component_route_family_promotion_router_inventory_delta_witness_minting_preflight"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_witness_minting_denial_report",
            "surfaces": ["component_route_family_promotion_router_inventory_delta_witness_minting_denial_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_witness_remediation_plan",
            "surfaces": ["component_route_family_promotion_router_inventory_delta_witness_remediation_plan"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request",
            "surfaces": ["component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger",
            "surfaces": [
                "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger"
            ],
            "status": "closed",
        },
        {
            "action_id": "publish_component_graph",
            "surfaces": ["component_graph"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_dead_detector",
            "surfaces": ["component_dead_detector"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_lifecycle_transition_receipts",
            "surfaces": ["component_lifecycle_transition_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_component_authority_envelope_witnesses",
            "surfaces": ["component_authority_envelope_witnesses"],
            "status": "closed",
        },
        {
            "action_id": "register_holistic_loop_read_model_kernel",
            "surfaces": ["holistic_loop_read_model_kernel"],
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
            "action_id": "classify_gateway_capability_admission_routes",
            "surfaces": ["gateway_capability_fabric", "capability_worker_execution", "trust_ledger"],
            "status": "closed",
        },
        {
            "action_id": "publish_local_assurance_refresh_contract",
            "surfaces": ["local_assurance_refresh"],
            "status": "closed",
        },
        {
            "action_id": "bound_authority_read_models_to_paginated_windows",
            "surfaces": ["gateway_approval_resolution", "authority_obligation_mesh"],
            "status": "closed",
        },
        {
            "action_id": "bind_approval_engine_mutations_to_effect_receipts",
            "surfaces": ["approval_engine_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "bind_effect_graph_commits_to_effect_receipts",
            "surfaces": ["effect_assurance_graph_commit"],
            "status": "closed",
        },
        {
            "action_id": "persist_effect_graph_commit_receipts",
            "surfaces": ["effect_assurance_graph_commit"],
            "status": "closed",
        },
        {
            "action_id": "wire_effect_graph_commit_receipt_store_into_bootstrap",
            "surfaces": ["effect_assurance_graph_commit"],
            "status": "closed",
        },
        {
            "action_id": "bind_job_engine_mutations_to_effect_receipts",
            "surfaces": ["job_engine_lifecycle"],
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
            "action_id": "classify_operator_console_read_model_routes",
            "surfaces": ["operator_console_read_models"],
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
            "action_id": "expose_federated_policy_sync_control_routes",
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
            "action_id": "classify_event_bus_operations_routes",
            "surfaces": ["event_bus_operations"],
            "status": "closed",
        },
        {
            "action_id": "classify_api_key_lifecycle_routes",
            "surfaces": ["api_key_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_operational_platform_read_model_routes",
            "surfaces": ["operational_platform_read_models"],
            "status": "closed",
        },
        {
            "action_id": "classify_conversation_memory_routes",
            "surfaces": ["conversation_memory_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_coordination_checkpoint_routes",
            "surfaces": ["coordination_checkpoint_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_engineering_puzzle_routes",
            "surfaces": ["engineering_puzzle_governance"],
            "status": "closed",
        },
        {
            "action_id": "classify_data_export_routes",
            "surfaces": ["data_export_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_prompt_template_routes",
            "surfaces": ["prompt_template_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_replay_trace_routes",
            "surfaces": ["replay_trace_read_models"],
            "status": "closed",
        },
        {
            "action_id": "classify_schema_validation_routes",
            "surfaces": ["schema_validation_registry"],
            "status": "closed",
        },
        {
            "action_id": "classify_semantic_search_routes",
            "surfaces": ["semantic_search_read_models"],
            "status": "closed",
        },
        {
            "action_id": "classify_task_queue_lifecycle_routes",
            "surfaces": ["task_queue_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_trace_observability_routes",
            "surfaces": ["trace_observability_read_models"],
            "status": "closed",
        },
        {
            "action_id": "classify_agent_memory_lifecycle_routes",
            "surfaces": ["agent_memory_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_governance_explanation_lifecycle_routes",
            "surfaces": ["governance_explanation_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_tool_registry_read_model_routes",
            "surfaces": ["tool_registry_read_models", "tool_invocation"],
            "status": "closed",
        },
        {
            "action_id": "expose_tool_permission_registry_operator_routes",
            "surfaces": ["tool_permission_registry"],
            "status": "closed",
        },
        {
            "action_id": "classify_structured_output_validation_routes",
            "surfaces": ["structured_output_validation"],
            "status": "closed",
        },
        {
            "action_id": "classify_operational_health_read_model_routes",
            "surfaces": ["operational_health_read_models"],
            "status": "closed",
        },
        {
            "action_id": "classify_agent_orchestration_lifecycle_routes",
            "surfaces": ["agent_orchestration_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_workflow_execution_lifecycle_routes",
            "surfaces": ["workflow_execution_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "bind_workflow_lifecycle_mutations_to_effect_receipts",
            "surfaces": ["workflow_execution_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_agent_chain_execution_routes",
            "surfaces": ["agent_chain_execution_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_certification_daemon_lifecycle_routes",
            "surfaces": ["certification_daemon_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_live_path_certification_routes",
            "surfaces": ["live_path_certification_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_runtime_state_persistence_routes",
            "surfaces": ["runtime_state_persistence_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_ops_diagnostics_routes",
            "surfaces": ["ops_proof_surface"],
            "status": "closed",
        },
        {
            "action_id": "classify_tenant_governance_lifecycle_routes",
            "surfaces": ["tenant_governance_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "classify_rbac_access_governance_routes",
            "surfaces": ["rbac_access_governance"],
            "status": "closed",
        },
        {
            "action_id": "classify_runtime_config_management_routes",
            "surfaces": ["runtime_config_management"],
            "status": "closed",
        },
        {
            "action_id": "classify_webhooks_routes",
            "surfaces": ["webhooks_proof_surface"],
            "status": "closed",
        },
        {
            "action_id": "classify_agent_adapter_protocol_routes",
            "surfaces": ["agent_adapter_protocol"],
            "status": "closed",
        },
        {
            "action_id": "classify_assistant_kernel_planning_routes",
            "surfaces": ["assistant_kernel_planning"],
            "status": "closed",
        },
        {
            "action_id": "classify_runbook_learning_routes",
            "surfaces": ["runbook_learning_lifecycle"],
            "status": "closed",
        },
        {
            "action_id": "publish_software_outcome_learning_contract",
            "surfaces": ["software_outcome_learning"],
            "status": "closed",
        },
        {
            "action_id": "publish_runtime_conformance_attestation",
            "surfaces": ["runtime_conformance_attestation"],
            "status": "closed",
        },
        {
            "action_id": "publish_proof_route_gap_triage_report",
            "surfaces": ["proof_route_gap_triage", "runtime_conformance_attestation"],
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
            "action_id": "publish_oidc_jwks_refresh_evidence_contract",
            "surfaces": ["oidc_jwks_refresh_evidence"],
            "status": "closed",
        },
        {
            "action_id": "publish_trusted_identity_header_boundary_contract",
            "surfaces": ["trusted_identity_header_boundary"],
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
            "action_id": "classify_world_state_knowledge_routes",
            "surfaces": ["governed_operational_intelligence"],
            "status": "closed",
        },
        {
            "action_id": "classify_policy_simulation_routes",
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
            "action_id": "publish_capability_manifest_registry_contract",
            "surfaces": ["capability_manifest_registry"],
            "status": "closed",
        },
        {
            "action_id": "publish_networked_worker_mesh_contract",
            "surfaces": ["networked_worker_mesh"],
            "status": "closed",
        },
        {
            "action_id": "publish_read_only_first_worker_path_contract",
            "surfaces": ["read_only_first_worker_path"],
            "status": "closed",
        },
        {
            "action_id": "publish_read_only_document_worker_path_contract",
            "surfaces": ["read_only_document_worker_path"],
            "status": "closed",
        },
        {
            "action_id": "publish_read_only_search_worker_path_contract",
            "surfaces": ["read_only_search_worker_path"],
            "status": "closed",
        },
        {
            "action_id": "publish_channel_approval_strength_policy_contract",
            "surfaces": ["channel_approval_strength_policy"],
            "status": "closed",
        },
        {
            "action_id": "publish_software_dev_capability_pack_contract",
            "surfaces": ["software_dev_capability_pack"],
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
            "action_id": "classify_governed_connector_routes",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_durable_gmail_oauth_operator_handoff_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_operator_handoff_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_live_probe_approval_binding_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_live_probe_authority_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_live_probe_operator_input_request_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_live_probe_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_observation_routing_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_approval_queue_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_approval_decision_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_send_preparation_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_send_execution_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_sent_message_observation_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_terminal_closure_review_packet_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_terminal_closure_certificate_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_terminal_closure_evidence_bundle_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_terminal_closure_anchor_preflight_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "publish_team_ops_shared_inbox_terminal_closure_anchor_receipt_contract",
            "surfaces": ["governed_connector_framework"],
            "status": "closed",
        },
        {
            "action_id": "classify_governed_scheduler_routes",
            "surfaces": ["governed_background_scheduler"],
            "status": "closed",
        },
        {
            "action_id": "classify_multi_agent_coordination_routes",
            "surfaces": ["multi_agent_coordination_runtime"],
            "status": "closed",
        },
        {
            "action_id": "publish_connector_self_healing_receipt_contract",
            "surfaces": ["connector_self_healing"],
            "status": "closed",
        },
        {
            "action_id": "publish_connector_action_promotion_gate_contract",
            "surfaces": ["connector_action_promotion_gate"],
            "status": "closed",
        },
        {
            "action_id": "publish_readiness_waiver_review_packet_contract",
            "surfaces": ["readiness_waiver_review_packet"],
            "status": "closed",
        },
        {
            "action_id": "publish_browser_observation_receipt_contract",
            "surfaces": ["browser_observation_receipt"],
            "status": "closed",
        },
        {
            "action_id": "publish_trusted_capture_evidence_packet_contract",
            "surfaces": ["trusted_capture_evidence_packet"],
            "status": "closed",
        },
        {
            "action_id": "publish_sccml_trace_adapter_witness_contract",
            "surfaces": ["sccml_trace_adapter_witness"],
            "status": "closed",
        },
        {
            "action_id": "publish_chaos_rehearsal_execution_report_contract",
            "surfaces": ["chaos_rehearsal_execution_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_invariant_fuzz_execution_report_contract",
            "surfaces": ["invariant_fuzz_execution_report"],
            "status": "closed",
        },
        {
            "action_id": "publish_research_source_conflict_map_contract",
            "surfaces": ["research_source_conflict_map"],
            "status": "closed",
        },
        {
            "action_id": "publish_worker_receipt_ledger_read_model_contract",
            "surfaces": ["worker_receipt_ledger_read_model"],
            "status": "closed",
        },
        {
            "action_id": "publish_mfidel_substrate_conformance_receipt_contract",
            "surfaces": ["mfidel_substrate_conformance_receipt"],
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
            "action_id": "bind_shell_execution_receipts_to_effect_assurance",
            "surfaces": ["shell_execution_adapter"],
            "status": "closed",
        },
        {
            "action_id": "publish_memory_lattice_admission_contract",
            "surfaces": ["memory_lattice"],
            "status": "closed",
        },
        {
            "action_id": "publish_p3_memory_topology_read_model_contract",
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
            "action_id": "publish_temporal_resolution_receipt_contract",
            "surfaces": ["temporal_resolution"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_sla_receipt_contract",
            "surfaces": ["temporal_sla"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_evidence_freshness_receipt_contract",
            "surfaces": ["temporal_evidence_freshness"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_reapproval_receipt_contract",
            "surfaces": ["temporal_reapproval"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_dispatch_window_receipt_contract",
            "surfaces": ["temporal_dispatch_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_budget_window_receipt_contract",
            "surfaces": ["temporal_budget_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_memory_receipt_contract",
            "surfaces": ["temporal_memory"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_causal_order_receipt_contract",
            "surfaces": ["temporal_causal_order"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_monotonic_duration_receipt_contract",
            "surfaces": ["temporal_monotonic_duration"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_accepted_risk_expiry_receipt_contract",
            "surfaces": ["temporal_accepted_risk_expiry"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_credential_expiry_receipt_contract",
            "surfaces": ["temporal_credential_expiry"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_retention_window_receipt_contract",
            "surfaces": ["temporal_retention_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_github_check_run_write_receipt_contract",
            "surfaces": ["github_check_run_write_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_github_app_token_exchange_receipt_contract",
            "surfaces": ["github_app_token_exchange_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_github_action_execution_receipt_contract",
            "surfaces": ["github_action_execution_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_github_branch_protection_reconcile_receipt_contract",
            "surfaces": ["github_branch_protection_reconcile_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_distributed_lease_claim_receipt_contract",
            "surfaces": ["distributed_lease_claim_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_distributed_lease_adapter_registry_receipt_contract",
            "surfaces": ["distributed_lease_adapter_registry_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_distributed_lease_execution_receipt_contract",
            "surfaces": ["distributed_lease_execution_receipts"],
            "status": "closed",
        },
        {
            "action_id": "publish_scheduler_worker_runtime_receipt_handoff_contract",
            "surfaces": ["scheduler_worker_runtime_receipt_handoff"],
            "status": "closed",
        },
        {
            "action_id": "publish_scheduler_worker_runtime_receipt_emitter_dry_run_contract",
            "surfaces": ["scheduler_worker_runtime_receipt_emitter_dry_run"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_rate_limit_window_receipt_contract",
            "surfaces": ["temporal_rate_limit_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_retry_window_receipt_contract",
            "surfaces": ["temporal_retry_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_lease_window_receipt_contract",
            "surfaces": ["temporal_lease_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_idempotency_window_receipt_contract",
            "surfaces": ["temporal_idempotency_window"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_missed_run_receipt_contract",
            "surfaces": ["temporal_missed_run"],
            "status": "closed",
        },
        {
            "action_id": "publish_temporal_recurrence_window_receipt_contract",
            "surfaces": ["temporal_recurrence_window"],
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
        {
            "action_id": "publish_trust_ledger_anchor_submission_receipt_contract",
            "surfaces": ["trust_ledger"],
            "status": "closed",
        },
        {
            "action_id": "publish_trust_ledger_remote_submission_preflight_contract",
            "surfaces": ["trust_ledger"],
            "status": "closed",
        },
    ]
    surfaces = _merge_duplicate_surfaces(surfaces)
    closure_actions = _normalize_closure_actions(closure_actions)
    return {
        "schema_version": 1,
        "generated_by": "scripts/proof_coverage_matrix.py",
        "coverage_levels": COVERAGE_LEVELS,
        "coverage_states": COVERAGE_STATES,
        "coverage_summary": coverage_summary(surfaces),
        "evidence_quality": evidence_quality_report(surfaces),
        "witness_integrity": witness_integrity_report(surfaces),
        "surfaces": surfaces,
        "route_coverage": route_coverage_report(surfaces, discover_declared_routes()),
        "closure_actions": closure_actions,
    }


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _merge_witness_anchor_aliases(
    left: dict[str, list[str]] | None,
    right: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    """Merge runtime witness anchor aliases without losing declaration order."""

    merged: dict[str, list[str]] = {}
    for aliases_by_witness in (left or {}, right or {}):
        for witness, aliases in aliases_by_witness.items():
            merged[witness] = _ordered_unique([*merged.get(witness, []), *aliases])
    return merged


def _merge_duplicate_surfaces(surfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []
    contract_keys = ("request_proof", "action_proof", "audit", "coverage_state")
    for surface in surfaces:
        surface_id = surface["surface_id"]
        if surface_id not in merged:
            surface_record = {
                **surface,
                "representative_paths": list(surface["representative_paths"]),
                "evidence_files": list(surface["evidence_files"]),
                "runtime_witnesses": list(surface.get("runtime_witnesses", [])),
            }
            anchor_aliases = _merge_witness_anchor_aliases(
                None,
                surface.get("runtime_witness_anchor_aliases"),
            )
            if anchor_aliases:
                surface_record["runtime_witness_anchor_aliases"] = anchor_aliases
            else:
                surface_record.pop("runtime_witness_anchor_aliases", None)
            merged[surface_id] = surface_record
            ordered_ids.append(surface_id)
            continue
        existing = merged[surface_id]
        for key in contract_keys:
            if existing[key] != surface[key]:
                raise ValueError(f"Conflicting proof coverage contract for surface {surface_id}: {key}")
        existing["representative_paths"] = _ordered_unique(
            [*existing["representative_paths"], *surface["representative_paths"]]
        )
        existing["evidence_files"] = _ordered_unique([*existing["evidence_files"], *surface["evidence_files"]])
        existing["runtime_witnesses"] = _ordered_unique(
            [*existing.get("runtime_witnesses", []), *surface.get("runtime_witnesses", [])]
        )
        anchor_aliases = _merge_witness_anchor_aliases(
            existing.get("runtime_witness_anchor_aliases"),
            surface.get("runtime_witness_anchor_aliases"),
        )
        if anchor_aliases:
            existing["runtime_witness_anchor_aliases"] = anchor_aliases
        else:
            existing.pop("runtime_witness_anchor_aliases", None)
    return [merged[surface_id] for surface_id in ordered_ids]


def _normalize_closure_actions(closure_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for action in closure_actions:
        normalized.append(
            {
                **action,
                "surfaces": _ordered_unique(action["surfaces"]),
            }
        )
    return normalized


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


def evidence_quality_report(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    """Return witness-strength gaps for classified proof surfaces."""
    quality_records: list[dict[str, Any]] = []
    by_strength = {
        "strong": 0,
        "classified_with_quality_gaps": 0,
        "unproven": 0,
    }

    for surface in surfaces:
        evidence_files = surface.get("evidence_files", [])
        runtime_witnesses = surface.get("runtime_witnesses", [])
        gaps: list[str] = []
        if surface["coverage_state"] == "unproven":
            gaps.append("surface_unproven")
        if surface["coverage_state"] in {"proven", "witnessed"} and not evidence_files:
            gaps.append("missing_evidence_file")
        if surface["coverage_state"] in {"proven", "witnessed"} and not runtime_witnesses:
            gaps.append("missing_runtime_witness")

        if surface["coverage_state"] == "unproven":
            strength = "unproven"
        elif gaps:
            strength = "classified_with_quality_gaps"
        else:
            strength = "strong"
        by_strength[strength] += 1
        if gaps:
            quality_records.append(
                {
                    "surface_id": surface["surface_id"],
                    "coverage_state": surface["coverage_state"],
                    "strength": strength,
                    "gaps": gaps,
                    "evidence_file_count": len(evidence_files),
                    "runtime_witness_count": len(runtime_witnesses),
                }
            )

    return {
        "by_strength": by_strength,
        "quality_gap_count": len(quality_records),
        "quality_gaps": quality_records,
    }


def witness_integrity_report(
    surfaces: list[dict[str, Any]],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Return exact test-function anchors for runtime witness labels."""
    surface_records: list[dict[str, Any]] = []
    anchored_count = 0
    unanchored_count = 0
    witness_count = 0

    for surface in surfaces:
        test_anchors = _test_function_anchors(surface.get("evidence_files", []), repo_root=repo_root)
        witness_anchor_aliases = surface.get("runtime_witness_anchor_aliases", {})
        anchored_witnesses: list[dict[str, Any]] = []
        unanchored_witnesses: list[str] = []
        for witness in surface.get("runtime_witnesses", []):
            witness_count += 1
            matching_anchors = list(test_anchors.get(witness, []))
            for alias in witness_anchor_aliases.get(witness, []):
                matching_anchors.extend(test_anchors.get(alias, []))
            matching_anchors = _ordered_unique(matching_anchors)
            if matching_anchors:
                anchored_count += 1
                anchored_witnesses.append({"witness": witness, "anchors": matching_anchors})
                continue
            unanchored_count += 1
            unanchored_witnesses.append(witness)
        if anchored_witnesses or unanchored_witnesses:
            surface_records.append(
                {
                    "surface_id": surface["surface_id"],
                    "runtime_witness_count": len(surface.get("runtime_witnesses", [])),
                    "exact_test_anchor_count": len(anchored_witnesses),
                    "unanchored_witness_count": len(unanchored_witnesses),
                    "anchored_witnesses": anchored_witnesses,
                    "unanchored_witnesses": unanchored_witnesses,
                }
            )

    return {
        "runtime_witness_count": witness_count,
        "exact_test_anchor_count": anchored_count,
        "unanchored_witness_count": unanchored_count,
        "surfaces": surface_records,
    }


def _test_function_anchors(evidence_files: list[str], repo_root: Path = REPO_ROOT) -> dict[str, list[str]]:
    anchors: dict[str, list[str]] = {}
    for evidence_file in evidence_files:
        if not evidence_file.endswith(".py"):
            continue
        if "/test" not in evidence_file.replace("\\", "/"):
            continue
        evidence_path = repo_root / evidence_file
        if not evidence_path.exists():
            continue
        try:
            parsed = ast.parse(evidence_path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(parsed):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            witness = node.name.removeprefix("test_")
            anchors.setdefault(witness, []).append(f"{evidence_file}::{node.name}")
    return anchors


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
        "/browser",
        "/document",
        "/email-calendar",
        "/messaging",
        "/phone",
        "/voice",
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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary_path.write_text(text, encoding="utf-8", newline="\n")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_matrix(path: Path, matrix: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(matrix, indent=2, sort_keys=True) + "\n")


def _markdown_cell(value: object) -> str:
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value) if value else "none"
    else:
        text = str(value) if value else "none"
    return text.replace("|", "\\|").replace("\n", " ")


def operator_document(matrix: dict[str, Any]) -> str:
    """Return the operator-readable proof coverage witness."""
    summary = matrix["coverage_summary"]
    evidence_quality = matrix["evidence_quality"]
    witness_integrity = matrix["witness_integrity"]
    route_coverage = matrix["route_coverage"]
    route_count = route_coverage["route_count"]
    unclassified_count = route_coverage["unclassified_route_count"]
    classified_count = route_count - unclassified_count
    completeness = round((classified_count / route_count) * 100) if route_count else 100

    lines = [
        "# Proof Coverage Matrix",
        "",
        "Purpose: define the current request-proof, action-proof, runtime-witness, and audit-chain coverage for externally callable MCOI and gateway surfaces.",
        "",
        "Governance scope: this document summarizes the canonical matrix generated by `scripts/proof_coverage_matrix.py`. The JSON fixture is the machine witness; this document is the operator-readable witness.",
        "",
        "| Surface | Representative paths | Request proof | Action proof | Runtime witnesses | Audit | Coverage state | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for surface in matrix["surfaces"]:
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                surface["surface_id"],
                _markdown_cell(surface.get("representative_paths", [])),
                _markdown_cell(surface.get("request_proof", "")),
                _markdown_cell(surface.get("action_proof", "")),
                _markdown_cell(surface.get("runtime_witnesses", [])),
                _markdown_cell(surface.get("audit", "")),
                _markdown_cell(surface.get("coverage_state", "")),
                _markdown_cell(surface.get("notes", "")),
            )
        )

    lines.extend(
        [
            "",
            "Coverage summary:",
            "",
            "| Metric | Count |",
            "|---|---:|",
            f"| Total surfaces | {summary['surface_count']} |",
            f"| Proven surfaces | {summary['by_coverage_state']['proven']} |",
            f"| Witnessed surfaces | {summary['by_coverage_state']['witnessed']} |",
            f"| Unproven surfaces | {summary['by_coverage_state']['unproven']} |",
            f"| Declared proof-relevant routes | {route_count} |",
            f"| Classified declared routes | {classified_count} |",
            f"| Unclassified declared routes | {unclassified_count} |",
            "",
            "Evidence quality audit:",
            "",
            "| Metric | Count |",
            "|---|---:|",
            f"| Strong classified surfaces | {evidence_quality['by_strength']['strong']} |",
            (
                "| Classified surfaces with quality gaps | "
                f"{evidence_quality['by_strength']['classified_with_quality_gaps']} |"
            ),
            f"| Unproven surfaces | {evidence_quality['by_strength']['unproven']} |",
            f"| Evidence quality gaps | {evidence_quality['quality_gap_count']} |",
            "",
            "Witness integrity audit:",
            "",
            "| Metric | Count |",
            "|---|---:|",
            f"| Runtime witness labels | {witness_integrity['runtime_witness_count']} |",
            f"| Exact test anchors | {witness_integrity['exact_test_anchor_count']} |",
            f"| Unanchored witness labels | {witness_integrity['unanchored_witness_count']} |",
            "",
            "Evidence quality gaps:",
        ]
    )
    if evidence_quality["quality_gaps"]:
        lines.extend(["", "| Surface | Strength | Gaps | Evidence files | Runtime witnesses |", "|---|---|---|---:|---:|"])
        for record in evidence_quality["quality_gaps"]:
            lines.append(
                "| `{}` | {} | {} | {} | {} |".format(
                    record["surface_id"],
                    _markdown_cell(record["strength"]),
                    _markdown_cell(record["gaps"]),
                    record["evidence_file_count"],
                    record["runtime_witness_count"],
                )
            )
    else:
        lines.append("none")

    lines.extend(["", "Witness integrity gaps:"])
    unanchored_surfaces = [
        record for record in witness_integrity["surfaces"] if record["unanchored_witness_count"]
    ]
    if unanchored_surfaces:
        lines.extend(["", "| Surface | Exact anchors | Unanchored | Unanchored labels |", "|---|---:|---:|---|"])
        for record in unanchored_surfaces:
            lines.append(
                "| `{}` | {} | {} | {} |".format(
                    record["surface_id"],
                    record["exact_test_anchor_count"],
                    record["unanchored_witness_count"],
                    _markdown_cell(record["unanchored_witnesses"]),
                )
            )
    else:
        lines.append("none")

    lines.extend(
        [
            "",
            "Resolved closure actions:",
            "",
        ]
    )
    closed_actions = [action for action in matrix["closure_actions"] if action["status"] == "closed"]
    open_actions = [action for action in matrix["closure_actions"] if action["status"] != "closed"]
    for index, action in enumerate(closed_actions, 1):
        lines.append(f"{index}. `{action['action_id']}`")

    lines.extend(["", "Open closure actions:"])
    if open_actions:
        lines.append("")
        for index, action in enumerate(open_actions, 1):
            lines.append(f"{index}. `{action['action_id']}`")
    else:
        lines.append("none")

    open_issues = []
    if unclassified_count:
        open_issues.append(
            f"{unclassified_count} proof-relevant declared routes remain unclassified and are marked unproven in the machine witness"
        )
    if evidence_quality["quality_gap_count"]:
        open_issues.append(
            f"{evidence_quality['quality_gap_count']} classified surfaces need stronger runtime-witness labels"
        )
    if witness_integrity["unanchored_witness_count"]:
        open_issues.append(
            f"{witness_integrity['unanchored_witness_count']} runtime-witness labels lack exact test-function anchors"
        )
    open_issue = "; ".join(open_issues) if open_issues else "none"
    verified_invariants = [
        "route declarations",
        "route-level coverage classification",
        "coverage levels",
        "coverage states",
        "closure action mapping",
        "schema contract validation",
        "deployment orchestration receipt schema contract",
    ]
    lines.extend(
        [
            "",
            "STATUS:",
            f"  Completeness: {completeness}%",
            f"  Invariants verified: {', '.join(verified_invariants)}",
            f"  Open issues: {open_issue}",
            (
                "  Next action: classify remaining unproven declared routes into named proof surfaces or explicit exemptions"
                if unclassified_count
                else "  Next action: strengthen classified surfaces that still lack runtime-witness labels"
                if evidence_quality["quality_gap_count"]
                else "  Next action: bind unanchored runtime-witness labels to exact test-function anchors"
                if witness_integrity["unanchored_witness_count"]
                else "  Next action: collect live deployment witness and apply public health declaration with approval"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_operator_document(path: Path, matrix: dict[str, Any]) -> None:
    _atomic_write_text(path, operator_document(matrix))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate or validate the proof coverage matrix.")
    parser.add_argument("--output", type=Path, default=CANONICAL_OUTPUT)
    parser.add_argument("--doc-output", type=Path, default=DOC_OUTPUT)
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
        expected_doc = operator_document(matrix)
        actual_doc = args.doc_output.read_text(encoding="utf-8")
        if actual_doc != expected_doc:
            raise SystemExit(f"{args.doc_output} is stale; run scripts/proof_coverage_matrix.py")
        if args.assurance_output.exists():
            actual_assurance = args.assurance_output.read_text(encoding="utf-8")
            if actual_assurance != expected:
                raise SystemExit(f"{args.assurance_output} is stale; run scripts/proof_coverage_matrix.py")
        return 0
    write_matrix(args.output, matrix)
    write_matrix(args.assurance_output, matrix)
    write_operator_document(args.doc_output, matrix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
