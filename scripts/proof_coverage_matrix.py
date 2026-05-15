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
        "universal_action_proof_replays_from_command_events",
        "operator_universal_action_read_model_filters_command_proofs",
        "operator_universal_action_console_renders_replay_state",
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
                "/operator/universal-actions/read-model",
                "/operator/universal-actions",
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
                "tests/test_gateway/test_capability_capsule_installer.py",
                "tests/test_gateway/test_webhooks.py",
                "tests/test_governed_capability_fabric.py",
            ],
            "Gateway command admission, request receipt envelopes, terminal closure, universal action proof replay, capsule compiler certification-evidence manifests, and the capsule admission installer receipt expose runtime witnesses.",
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
        ),
        _surface(
            "capability_worker_execution",
            ["/capability/execute"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/capability_worker.py",
                "gateway/capability_isolation.py",
                "gateway/capability_dispatch.py",
                "tests/test_gateway/test_capability_worker.py",
            ],
            "Restricted capability worker execution accepts only signed, hash-bound, isolated capability requests and returns signed receipt-bearing execution responses.",
            [
                "signed_capability_request_required",
                "response_signature_verified",
                "input_hash_mismatch_rejected",
                "intent_boundary_mismatch_rejected",
                "non_isolated_boundary_rejected",
                "local_smoke_stub_bound_to_local_environment",
            ],
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/llm/completion.py",
                "mcoi/mcoi_runtime/app/routers/llm/chat.py",
                "mcoi/mcoi_runtime/app/streaming.py",
                "mcoi/tests/test_streaming.py",
                "mcoi/tests/test_server_phase200.py",
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
        ),
        _surface(
            "assistant_kernel_planning",
            [
                "/api/v1/assistant/profiles",
                "/api/v1/assistant/finance-ops/plans",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/assistant.py",
                "mcoi/mcoi_runtime/assistant_kernel/planner.py",
                "mcoi/mcoi_runtime/assistant_kernel/identity.py",
                "mcoi/tests/test_assistant_router.py",
                "tests/test_assistant_kernel.py",
            ],
            "Assistant kernel routes expose governed profile read models and compile FinanceOps plans with consent, approval, idempotency, effect reconciliation, and closure controls without executing external effects.",
            [
                "assistant_profiles_read_model_bounded",
                "finance_ops_plan_requires_active_consent",
                "finance_ops_plan_projects_operator_queue",
                "assistant_plan_never_grants_execution_authority",
                "assistant_plan_errors_sanitized",
            ],
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
            "Operational platform read-model routes aggregate bounded bootstrap, LLM history, dependency, feature-flag, metric, rate-limit, SLA, and gateway status state without mutation authority.",
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
            "witnessed",
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
            "witnessed",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/prompts.py",
                "mcoi/mcoi_runtime/core/prompt_template_engine.py",
                "mcoi/tests/test_prompt_template_engine.py",
                "mcoi/tests/test_prompt_templates.py",
                "mcoi/tests/test_server_phase209.py",
            ],
            "Prompt template routes list bounded template metadata, render declared variables, and sanitize optional execution failures behind the LLM circuit breaker.",
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
            "witnessed",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/tenant.py",
                "mcoi/mcoi_runtime/governance/guards/budget.py",
                "mcoi/mcoi_runtime/governance/guards/tenant_gating.py",
                "mcoi/tests/test_server_phase202.py",
                "mcoi/tests/test_governance_endpoints.py",
                "mcoi/tests/test_tenant_budget.py",
                "mcoi/tests/test_tenant_gating.py",
                "mcoi/tests/test_tenant_ledger.py",
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
            "witnessed",
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
            ],
            "API webhook management routes bind subscription mutation, tenant-scoped subscription read models, delivery history, retry summary, dead-letter read models, and workflow delivery evidence to governed runtime state, audit records, and bounded retry failure evidence.",
            [
                "webhook_subscribe_records_audit",
                "webhook_subscription_audited",
                "webhook_subscription_mutation_receipt_emitted",
                "webhook_list_is_tenant_scoped",
                "webhook_subscription_list_bounded",
                "webhook_delivery_history_is_bounded",
                "webhook_delivery_mutation_receipts_exposed",
                "webhook_delivery_history_bounded",
                "webhook_flow_records_delivery",
                "webhook_delivery_queue_mutation_receipt_emitted",
                "webhook_mutation_receipt_closes_effect_assurance",
                "webhook_retry_summary_is_bounded",
                "webhook_retry_summary_governed",
                "webhook_dead_letters_are_explicit",
                "webhook_dead_letters_bounded",
                "webhook_workflow_delivery_witnessed",
                "webhook_delivery_errors_are_sanitized",
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
            ],
            "read_model",
            "read_model",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/console.py",
                "mcoi/mcoi_runtime/app/console.py",
                "mcoi/mcoi_runtime/app/view_models.py",
                "mcoi/tests/test_operator_console.py",
                "mcoi/tests/test_console.py",
            ],
            "Operator console routes expose bounded read-only runtime, audit, checkpoint, provider, scheduler, and aggregate views with governed response witnesses.",
            [
                "console_home_returns_governed_runtime_vitals",
                "console_runs_bounds_recent_audit_entries",
                "console_audit_exposes_chain_intact_read_model",
                "console_checkpoints_expose_persisted_state_summary",
                "console_provider_and_scheduler_views_are_read_only",
            ],
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
            [
                "policy_version_register_and_fetch",
                "policy_version_promote_diff_shadow_and_rollback",
                "policy_version_routes_fail_closed",
                "policy_artifact_hash_is_deterministic",
                "policy_registry_promotes_and_rolls_back_versions",
                "policy_diff_reports_changed_and_added_rules",
                "shadow_governance_compares_without_promoting",
                "registry_fails_closed_on_unknown_versions",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/pilot.py",
                "mcoi/mcoi_runtime/app/pilot_init.py",
                "mcoi/tests/test_pilot_init.py",
                "docs/47_one_command_pilot_bringup.md",
            ],
            "Pilot provisioning returns deterministic scaffold artifacts, persists accepted provision records, and exposes bounded operator history read models.",
            [
                "initialize_pilot_writes_complete_artifact_set",
                "initialize_pilot_is_deterministic_for_same_inputs",
                "build_pilot_scaffold_has_no_filesystem_side_effects",
                "pilot_provision_registry_persists_bounded_records",
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
            ["/api/v1/federation/summary"],
            "read_model",
            "read_model",
            "read_model",
            "witnessed",
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
            "Federated control-plane summary exposes signed policy distribution and local enforcement receipts without tenant data replication.",
            [
                "signed_policy_metadata_only_sync",
                "invalid_signature_denied_before_local_acceptance",
                "policy_not_allowed_for_cluster_denied",
                "unsynced_policy_denied_locally",
                "tenant_region_mismatch_denied_locally",
                "central_data_transfer_forbidden",
                "federated_snapshot_schema_valid",
            ],
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
            "witnessed",
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
            "witnessed",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/tools.py",
                "mcoi/mcoi_runtime/core/tool_use.py",
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_tool_use.py",
            ],
            "Tool registry read-model routes expose registered tool metadata, bounded invocation history, and LLM-compatible schemas while invocation remains governed by the tool_invocation action-proof surface.",
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
            "structured_output_validation",
            [
                "/api/v1/output/parse",
                "/api/v1/output/schemas",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
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
        ),
        _surface(
            "operational_health_read_models",
            [
                "/api/v1/health/deep",
                "/api/v1/health/score",
                "/api/v1/health/v2",
                "/api/v1/health/v3",
                "/api/v1/dashboard",
                "/api/v1/plugins",
                "/api/v1/guards",
                "/api/v1/capabilities",
                "/api/v1/readiness",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/health.py",
                "mcoi/mcoi_runtime/core/deep_health.py",
                "mcoi/mcoi_runtime/core/health_aggregator.py",
                "mcoi/mcoi_runtime/core/health_check_agg.py",
                "mcoi/mcoi_runtime/core/health_v3.py",
                "mcoi/mcoi_runtime/app/routers/ops/summaries.py",
                "mcoi/mcoi_runtime/app/routers/ops/release.py",
                "mcoi/mcoi_runtime/app/routers/ops/snapshots.py",
                "mcoi/tests/test_deep_health.py",
                "mcoi/tests/test_health_aggregator.py",
                "mcoi/tests/test_health_check_agg.py",
                "mcoi/tests/test_phase232.py",
                "mcoi/tests/test_server_phase205.py",
                "mcoi/tests/test_server_phase210.py",
            ],
            "Operational health routes expose bounded read models for deep component diagnostics, weighted health score, degraded-state checks, and v3 recovery tracking without mutation authority.",
            [
                "deep_health_components_bounded",
                "health_score_range_bounded",
                "health_score_components_weighted",
                "health_v2_degraded_state_supported",
                "health_v2_exception_sanitized",
                "health_v3_weighted_aggregation",
                "health_v3_recovery_tracking",
                "health_routes_return_read_models",
                "ops_dashboard_read_model_bounded",
                "production_readiness_checks_bounded",
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
                "/api/v1/pipeline/execute",
                "/api/v1/pipeline/history",
                "/api/v1/templates",
                "/api/v1/templates/execute",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "gateway/workflow_orchestration.py",
                "mcoi/mcoi_runtime/app/routers/workflow.py",
                "mcoi/mcoi_runtime/core/agent_workflow.py",
                "mcoi/mcoi_runtime/core/traced_workflow.py",
                "tests/test_gateway/test_workflow_orchestration.py",
                "mcoi/tests/test_agent_workflow.py",
                "mcoi/tests/test_traced_workflow.py",
                "mcoi/tests/test_server_phase205.py",
            ],
            "Workflow execution routes execute governed multi-agent workflows with action proof receipts, expose bounded history read models, produce replay-traced workflow runs, and record workflow lifecycle mutation receipts as bounded Effect Assurance evidence.",
            [
                "workflow_execute_emits_action_proof",
                "workflow_invalid_capability_bounded",
                "workflow_history_bounded",
                "workflow_success_records_audit",
                "workflow_failure_records_audit",
                "workflow_errors_sanitized",
                "workflow_lifecycle_mutation_receipts_emitted",
                "workflow_failure_compensation_receipts_emitted",
                "workflow_mutation_receipt_closes_effect_assurance",
                "traced_workflow_emits_replay_trace",
                "traced_workflow_recorder_errors_sanitized",
                "legacy_execute_emits_action_proof",
                "session_read_model_bounded",
                "ledger_read_model_bounded",
                "pipeline_execution_emits_action_proof",
                "pipeline_history_bounded",
                "template_read_models_bounded",
                "template_execution_governed",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/agent.py",
                "mcoi/mcoi_runtime/core/agent_chain.py",
                "mcoi/tests/test_agent_chain.py",
                "mcoi/tests/test_server_phase215.py",
            ],
            "Agent chain routes execute ordered multi-step LLM chains, propagate prior outputs through templates, publish bounded completion events, sanitize failure details, and expose bounded execution history.",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/daemon.py",
                "mcoi/mcoi_runtime/core/certification_daemon.py",
                "mcoi/tests/test_certification_daemon.py",
                "mcoi/tests/test_server_phase200.py",
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
            "witnessed",
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
        ),
        _surface(
            "effect_assurance_graph_commit",
            [
                "EffectAssuranceGate.commit_graph",
                "EffectAssuranceGate.graph_commit_receipts",
                "EffectAssuranceGate.graph_commit_effect_records",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/core/effect_assurance.py",
                "mcoi/mcoi_runtime/core/operational_graph.py",
                "mcoi/tests/test_effect_assurance_core.py",
            ],
            "Effect Assurance graph commits emit bounded receipts for MATCH-only operational graph mutation and expose those receipts as actual effects for observation.",
            [
                "effect_graph_commit_requires_match",
                "effect_graph_commit_receipt_emitted",
                "effect_graph_commit_receipt_converts_to_actual_effect",
                "effect_graph_commit_receipt_closes_effect_assurance",
            ],
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
                "schemas/latest_anchor_read_model.schema.json",
                "schemas/runtime_witness.schema.json",
                "schemas/mullu_governance_protocol.manifest.json",
                "tests/test_gateway/test_webhooks.py",
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
                "closure_validation_report_matches_public_schema_for_not_published",
                "readiness_report_matches_public_schema",
                "receipt_validation_report_matches_public_schema",
                "protocol_manifest_indexes_deployment_orchestration_validation",
                "protocol_manifest_indexes_deployment_publication_closure_validation",
                "protocol_manifest_indexes_gateway_publication_readiness",
                "protocol_manifest_indexes_gateway_publication_receipt_validation",
                "protocol_manifest_indexes_runtime_witness_and_latest_anchor",
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
            "Governed operational intelligence binds sourced world-state admission, knowledge graph entity/link/contradiction routes, policy simulation dry-run APIs, compiled goal-plan certificates, and deterministic causal simulation receipts before effect-bearing execution.",
            [
                "world_assertions_require_source_evidence",
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
            "Software-development capability pack keeps repo intelligence, context building, gate planning, governed change execution, app task graph planning, and PR candidate preparation behind explicit capsule admission; default packs do not load it, read-only capabilities expose no execution authority, and effectful capabilities require sandboxing, approval, receipts, recovery evidence, and direct-deployment denial.",
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
                "software_dev_production_ready_overclaim_rejected",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/connectors.py",
                "mcoi/mcoi_runtime/core/connector_framework.py",
                "mcoi/tests/test_connector_framework.py",
                "mcoi/tests/test_server_phase217.py",
                "mcoi/tests/test_server_phase218.py",
            ],
            "Governed connector routes register typed connector definitions, invoke handlers through guard-chain admission, bound lifecycle enable/disable controls, expose bounded list/history/summary read models, and sanitize connector errors before returning operator-visible receipts.",
            [
                "connector_registration_typed",
                "connector_invocation_guard_chain_checked",
                "connector_lifecycle_disable_enable_bounded",
                "connector_history_summary_bounded",
                "connector_errors_sanitized",
                "connector_invocation_audited",
            ],
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
            "witnessed",
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
            "witnessed",
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
                "/evidence/bundles/{command_id}",
                "GET /evidence/bundles/{command_id}",
                "scripts/verify_evidence_bundle.py",
                "scripts/verify_anchor_receipt.py",
                "TrustLedger.package_anchor_export",
                "TrustLedgerBundle",
                "ExternalProofAnchorReceipt",
                "TrustLedgerExportPackage",
            ],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "docs/62_governed_operational_intelligence.md",
                "docs/65_trust_ledger_offline_verification.md",
                "gateway/evidence_bundle.py",
                "gateway/trust_ledger.py",
                "scripts/verify_evidence_bundle.py",
                "scripts/verify_anchor_receipt.py",
                "schemas/trust_ledger_anchor_receipt.schema.json",
                "schemas/trust_ledger_anchor_verification_report.schema.json",
                "schemas/trust_ledger_bundle.schema.json",
                "schemas/trust_ledger_bundle_verification_report.schema.json",
                "schemas/trust_ledger_evidence_artifacts.schema.json",
                "schemas/trust_ledger_export_package.schema.json",
                "tests/test_gateway/test_evidence_bundle_endpoint.py",
                "tests/test_gateway/test_trust_ledger_anchor_receipt.py",
                "tests/test_gateway/test_trust_ledger.py",
                "tests/test_verify_anchor_receipt.py",
            ],
            "Trust ledger signs terminal-closure evidence bundles, exposes operator bundle export, verifies exported bundle and anchor receipt files offline, emits external anchor receipts, and packages verifier inputs with content hashes for portable audit review.",
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
            "Temporal retention window rechecks data lifecycle actions for retention_until, delete_after, legal hold, tenant scope, owner, retention policy refs, evidence refs, source data decisions, and overdue timing before deletion, archive, anonymization, or retention review.",
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
                "temporal_retention_window_receipt_schema_valid",
                "receipt_not_terminal_closure",
            ],
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
            [
                "replay_determinism_endpoint_returns_match_report",
                "replay_determinism_endpoint_reports_unknown_operation",
                "replay_determinism_endpoint_missing_trace_fails_closed",
                "harness_reports_deterministic_match",
                "harness_report_hash_is_deterministic",
                "harness_reports_sequence_gap_before_replay",
                "harness_reports_operation_errors_bounded",
            ],
        ),
        _surface(
            "tool_invocation",
            ["/api/v1/tools/invoke", "/api/v1/workflow/tools"],
            "request_proof",
            "action_proof",
            "audit_chain",
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/data/tools.py",
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
                "mcoi/tests/test_server_phase212.py",
                "mcoi/tests/test_server_phase213.py",
                "mcoi/tests/test_server_runtime_helpers.py",
                "tests/test_gateway/test_mcp_capability_fabric.py",
                "tests/test_validate_mcp_capability_manifest.py",
                "tests/test_validate_mcp_operator_checklist.py",
            ],
            "Tool invocation and MCP capability import bind action proof ids, capability policy receipts, authority-obligation ownership records, validated operator manifests, and machine-readable handoff checklists.",
            [
                "invoke_tool",
                "invoke_tool_rejects_unsafe_expression",
                "invoke_unknown_tool",
                "tool_history",
                "tool_workflow",
                "tool_workflow_tool_calls_include_policy_receipts",
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
            "witnessed",
            [
                "mcoi/mcoi_runtime/app/routers/lineage.py",
                "mcoi/mcoi_runtime/core/lineage_query.py",
                "mcoi/tests/test_server_lineage.py",
                "docs/42_lineage_query_api.md",
                "schemas/lineage_query.schema.json",
                "schemas/trace_entry.schema.json",
                "schemas/replay_record.schema.json",
            ],
            "Lineage query API resolves read-only lineage:// URIs with bounded output, command, graph, and policy-version read models.",
            [
                "lineage_resolve_route_returns_trace_document",
                "lineage_trace_permalink_route_returns_document",
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
            "witnessed",
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
                "god_mode_capability_keys_are_unique",
                "god_mode_every_capability_declares_at_least_one_bypass",
                "god_mode_catastrophic_caps_require_dual_control",
                "god_mode_catastrophic_caps_are_one_shot",
                "god_mode_catastrophic_caps_have_short_ttl",
                "god_mode_secrets_capabilities_use_strictest_floor",
                "god_mode_agree_to_register_arms_capability",
                "god_mode_issue_ticket_requires_armed",
                "god_mode_double_consume_rejected",
                "god_mode_consume_ticket_emits_receipt",
                "god_mode_revoke_ticket_blocks_consume",
                "god_mode_withdraw_agreement_reverts_state",
                "god_mode_two_distinct_agreements_arm_capability",
                "god_mode_end_to_end_consent_chain",
            ],
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
            "action_id": "classify_gateway_capability_admission_routes",
            "surfaces": ["gateway_capability_fabric", "capability_worker_execution", "trust_ledger"],
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


def _merge_duplicate_surfaces(surfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []
    contract_keys = ("request_proof", "action_proof", "audit", "coverage_state")
    for surface in surfaces:
        surface_id = surface["surface_id"]
        if surface_id not in merged:
            merged[surface_id] = {
                **surface,
                "representative_paths": list(surface["representative_paths"]),
                "evidence_files": list(surface["evidence_files"]),
                "runtime_witnesses": list(surface.get("runtime_witnesses", [])),
            }
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
        anchored_witnesses: list[dict[str, Any]] = []
        unanchored_witnesses: list[str] = []
        for witness in surface.get("runtime_witnesses", []):
            witness_count += 1
            matching_anchors = test_anchors.get(witness, [])
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
                else "  Next action: advance sandboxed capability-worker execution closure"
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
