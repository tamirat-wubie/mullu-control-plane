"""Purpose: verify the generated proof coverage matrix witness.

Governance scope: prevents drift between route surfaces and the proof coverage
closure ledger.
Dependencies: scripts.proof_coverage_matrix, canonical JSON fixture, repository
source tree.
Invariants: coverage levels are bounded, evidence files exist, runtime witnesses
are explicit, and canonical fixture content is generated from code.
"""

from __future__ import annotations

import json

from scripts.proof_coverage_matrix import (
    ASSURANCE_OUTPUT,
    CANONICAL_OUTPUT,
    DOC_OUTPUT,
    REPO_ROOT,
    discover_declared_routes,
    operator_document,
    route_coverage_report,
    proof_coverage_matrix,
    validate_matrix_routes,
)


def _load_fixture() -> dict:
    return json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))


def test_fixture_contract_is_canonical() -> None:
    matrix = _load_fixture()

    assert matrix == proof_coverage_matrix()
    assert matrix["schema_version"] == 1
    assert matrix["generated_by"] == "scripts/proof_coverage_matrix.py"
    assert len(matrix["surfaces"]) >= 3


def test_surface_ids_are_unique_after_generation() -> None:
    matrix = _load_fixture()
    surface_ids = [surface["surface_id"] for surface in matrix["surfaces"]]

    assert len(surface_ids) == len(set(surface_ids))
    assert surface_ids.count("operational_platform_read_models") == 1
    assert all(surface_id for surface_id in surface_ids)


def test_coverage_levels_are_bounded() -> None:
    matrix = _load_fixture()
    coverage_levels = set(matrix["coverage_levels"])
    coverage_states = set(matrix["coverage_states"])

    assert {"gap", "request_proof", "action_proof", "audit_chain"} <= coverage_levels
    assert coverage_states == {"proven", "witnessed", "unproven"}
    assert all(surface["request_proof"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["action_proof"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["audit"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["coverage_state"] in coverage_states for surface in matrix["surfaces"])
    assert {"proven", "witnessed"} <= {surface["coverage_state"] for surface in matrix["surfaces"]}


def test_coverage_summary_matches_surfaces() -> None:
    matrix = _load_fixture()
    summary = matrix["coverage_summary"]
    surfaces = matrix["surfaces"]

    assert summary["surface_count"] == len(surfaces)
    assert sum(summary["by_coverage_state"].values()) == len(surfaces)
    assert sum(summary["by_request_proof"].values()) == len(surfaces)
    assert sum(summary["by_action_proof"].values()) == len(surfaces)
    assert sum(summary["by_audit"].values()) == len(surfaces)
    assert summary["by_coverage_state"]["unproven"] == 0
    assert summary["by_coverage_state"]["proven"] >= 1
    assert summary["by_coverage_state"]["witnessed"] >= 1


def test_declared_routes_have_explicit_coverage_classification() -> None:
    matrix = _load_fixture()
    report = matrix["route_coverage"]
    declared_report = route_coverage_report(matrix["surfaces"], discover_declared_routes())

    assert report == declared_report
    assert report["route_count"] == len(report["routes"])
    assert sum(report["by_coverage_state"].values()) == report["route_count"]
    assert report["unclassified_route_count"] == report["by_coverage_state"]["unproven"]
    assert all(record["coverage_state"] in matrix["coverage_states"] for record in report["routes"])
    assert all(record["surface_id"] for record in report["routes"])
    assert report["unclassified_route_count"] == 0
    assert all(record["surface_id"] != "unclassified_declared_route" for record in report["routes"])
    assert all(record["coverage_state"] != "unproven" for record in report["routes"])


def test_operational_platform_surface_owns_operational_read_model_routes() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    aggregate_routes = {
        route
        for route in surfaces["operational_platform_read_models"]["representative_paths"]
        if route.startswith("/")
    }

    assert aggregate_routes
    assert all(route_records[route]["surface_id"] == "operational_platform_read_models" for route in aggregate_routes)
    assert route_records["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert route_records["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert route_records["/gateway/status"]["surface_id"] == "operational_platform_read_models"


def test_representative_routes_are_not_unclassified() -> None:
    matrix = _load_fixture()
    classified_routes = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert classified_routes["/api/v1/lineage/resolve"]["surface_id"] == "lineage_query_api"
    assert classified_routes["/api/v1/lineage/artifact/{artifact_id}"]["surface_id"] == "lineage_query_api"
    assert classified_routes["/api/v1/stream"]["surface_id"] == "llm_streaming"
    assert classified_routes["/webhook/web"]["surface_id"] == "gateway_webhook_ingress"
    assert classified_routes["/capability-fabric/admission-audits"]["surface_id"] == "gateway_capability_fabric"
    assert classified_routes["/capability-fabric/capsule-admissions"]["surface_id"] == "gateway_capability_fabric"
    assert (
        classified_routes["/capability-fabric/capsule-admission-receipts"]["surface_id"]
        == "gateway_capability_fabric"
    )
    assert classified_routes["/commands/{command_id}/capability-admission"]["surface_id"] == "gateway_capability_fabric"
    assert classified_routes["/commands/{command_id}/authority"]["surface_id"] == "authority_obligation_mesh"
    assert classified_routes["/capability/execute"]["surface_id"] == "capability_worker_execution"
    assert classified_routes["/evidence/bundles/{command_id}"]["surface_id"] == "trust_ledger"
    assert classified_routes["/api/v1/data-governance/evaluate"]["surface_id"] == "data_governance_controls"
    assert classified_routes["/api/v1/compliance/audit-package"]["surface_id"] == "compliance_evidence_exports"
    assert classified_routes["/api/v1/runbooks/analyze"]["surface_id"] == "runbook_learning_lifecycle"
    assert classified_routes["/api/v1/runbooks/{runbook_id}/activate"]["surface_id"] == "runbook_learning_lifecycle"
    assert classified_routes["/api/v1/tenant/register"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/tenant/{tenant_id}/status"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/tenant/{tenant_id}/gate"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/usage/{tenant_id}"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/isolation/verify"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/api/v1/quotas/{tenant_id}"]["surface_id"] == "tenant_governance_lifecycle"
    assert classified_routes["/authority/operator"]["surface_id"] == "authority_operator_controls"
    assert classified_routes["/authority/ownership"]["surface_id"] == "authority_operator_controls"
    assert classified_routes["/api/v1/temporal/schedules"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/temporal/worker/tick"]["surface_id"] == "temporal_kernel"
    assert classified_routes["/api/v1/knowledge/entities"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/knowledge/contradictions/unresolved"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/simulate"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/simulate/history"]["surface_id"] == "governed_operational_intelligence"
    assert classified_routes["/api/v1/connectors/register"]["surface_id"] == "governed_connector_framework"
    assert classified_routes["/api/v1/connectors/invoke"]["surface_id"] == "governed_connector_framework"
    assert classified_routes["/api/v1/scheduler/jobs"]["surface_id"] == "governed_background_scheduler"
    assert classified_routes["/api/v1/scheduler/execute"]["surface_id"] == "governed_background_scheduler"
    assert (
        classified_routes["/api/v1/scheduler/jobs/{job_id}/disable"]["surface_id"]
        == "governed_background_scheduler"
    )
    assert classified_routes["/api/v1/multi-agent/delegate"]["surface_id"] == "multi_agent_coordination_runtime"
    assert classified_routes["/api/v1/multi-agent/merge"]["surface_id"] == "multi_agent_coordination_runtime"
    assert (
        classified_routes["/api/v1/multi-agent/conflicts/unresolved"]["surface_id"]
        == "multi_agent_coordination_runtime"
    )
    assert classified_routes["/api/v1/config"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/update"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/rollback"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/watcher"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/config/drift"]["surface_id"] == "runtime_config_management"
    assert classified_routes["/api/v1/events/publish"]["surface_id"] == "event_bus_operations"
    assert classified_routes["/api/v1/events"]["surface_id"] == "event_bus_operations"
    assert classified_routes["/api/v1/events/store/summary"]["surface_id"] == "event_bus_operations"
    assert classified_routes["/api/v1/ops/benchmarks"]["surface_id"] == "ops_proof_surface"
    assert classified_routes["/api/v1/ops/imports"]["surface_id"] == "ops_proof_surface"
    assert classified_routes["/api/v1/ops/proof-bridge"]["surface_id"] == "ops_proof_surface"
    assert classified_routes["/api/v1/api-keys"]["surface_id"] == "api_key_lifecycle"
    assert classified_routes["/api/v1/api-keys/{key_id}"]["surface_id"] == "api_key_lifecycle"
    assert classified_routes["/api/v1/queue/submit"]["surface_id"] == "task_queue_lifecycle"
    assert classified_routes["/api/v1/queue/process"]["surface_id"] == "task_queue_lifecycle"
    assert classified_routes["/api/v1/queue/result/{task_id}"]["surface_id"] == "task_queue_lifecycle"
    assert classified_routes["/api/v1/memory/store"]["surface_id"] == "agent_memory_lifecycle"
    assert classified_routes["/api/v1/memory/search"]["surface_id"] == "agent_memory_lifecycle"
    assert classified_routes["/api/v1/memory/summary"]["surface_id"] == "agent_memory_lifecycle"
    assert classified_routes["/api/v1/explain/action"]["surface_id"] == "governance_explanation_lifecycle"
    assert (
        classified_routes["/api/v1/explain/audit/{entry_index}"]["surface_id"]
        == "governance_explanation_lifecycle"
    )
    assert classified_routes["/api/v1/explain/summary"]["surface_id"] == "governance_explanation_lifecycle"
    assert classified_routes["/api/v1/tools"]["surface_id"] == "tool_registry_read_models"
    assert classified_routes["/api/v1/tools/history"]["surface_id"] == "tool_registry_read_models"
    assert classified_routes["/api/v1/tools/llm-format"]["surface_id"] == "tool_registry_read_models"
    assert classified_routes["/api/v1/tools/invoke"]["surface_id"] == "tool_invocation"
    assert classified_routes["/api/v1/output/parse"]["surface_id"] == "structured_output_validation"
    assert classified_routes["/api/v1/output/schemas"]["surface_id"] == "structured_output_validation"
    assert classified_routes["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/rate-limits/{client_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/flags/{flag_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/traces"]["surface_id"] == "trace_observability_read_models"
    assert classified_routes["/api/v1/traces/slow"]["surface_id"] == "trace_observability_read_models"
    assert classified_routes["/api/v1/traces/summary"]["surface_id"] == "trace_observability_read_models"
    assert classified_routes["/api/v1/health/deep"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/health/score"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/health/v3"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/readiness"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/deploy/readiness"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/release/latest"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/snapshot"]["surface_id"] == "operational_health_read_models"
    assert classified_routes["/api/v1/orchestration"]["surface_id"] == "agent_orchestration_lifecycle"
    assert classified_routes["/api/v1/orchestration/plans"]["surface_id"] == "agent_orchestration_lifecycle"
    assert (
        classified_routes["/api/v1/orchestration/plans/{plan_id}"]["surface_id"]
        == "agent_orchestration_lifecycle"
    )
    assert classified_routes["/api/v1/workflow/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/workflow/history"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/workflow/traced"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/pipeline/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/templates/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert classified_routes["/api/v1/chain/execute"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert classified_routes["/api/v1/chain/history"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert classified_routes["/api/v1/daemon/status"]["surface_id"] == "certification_daemon_lifecycle"
    assert classified_routes["/api/v1/daemon/tick"]["surface_id"] == "certification_daemon_lifecycle"
    assert classified_routes["/api/v1/daemon/force"]["surface_id"] == "certification_daemon_lifecycle"
    assert classified_routes["/api/v1/certify"]["surface_id"] == "live_path_certification_lifecycle"
    assert classified_routes["/api/v1/certify/history"]["surface_id"] == "live_path_certification_lifecycle"
    assert classified_routes["/api/v1/state"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert classified_routes["/api/v1/state/save"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert classified_routes["/api/v1/state/{state_type}"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert classified_routes["/api/v1/finance/approval-packets"]["surface_id"] == "finance_approval_packets"
    assert (
        classified_routes["/api/v1/finance/approval-packets/operator/read-model"]["surface_id"]
        == "finance_approval_packets"
    )
    assert (
        classified_routes["/api/v1/finance/approval-packets/{case_id}/proof"]["surface_id"]
        == "finance_approval_packets"
    )
    assert classified_routes["/api/v1/agent/register"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agent/action-request"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agent/restore"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agents"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/agents/{agent_id}/tasks"]["surface_id"] == "agent_adapter_protocol"
    assert classified_routes["/api/v1/webhooks/subscribe"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks/deliveries"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks/retry/summary"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/webhooks/retry/dead-letters"]["surface_id"] == "webhooks_proof_surface"
    assert classified_routes["/api/v1/rbac/identities"]["surface_id"] == "rbac_access_governance"
    assert classified_routes["/api/v1/rbac/roles"]["surface_id"] == "rbac_access_governance"
    assert classified_routes["/api/v1/rbac/bindings"]["surface_id"] == "rbac_access_governance"
    assert classified_routes["/api/v1/bootstrap"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/circuit-breaker"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/llm/history"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/conversation/message"]["surface_id"] == "conversation_memory_lifecycle"
    assert classified_routes["/api/v1/conversation/{conversation_id}"]["surface_id"] == "conversation_memory_lifecycle"
    assert classified_routes["/api/v1/conversations"]["surface_id"] == "conversation_memory_lifecycle"
    assert classified_routes["/api/v1/coordination/checkpoint"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert classified_routes["/api/v1/coordination/restore"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert classified_routes["/api/v1/dependencies"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/dependencies/{name}/impact"]["surface_id"] == "operational_platform_read_models"
    assert (
        classified_routes["/api/v1/engineering-puzzle/candidates/judge"]["surface_id"]
        == "engineering_puzzle_governance"
    )
    assert classified_routes["/api/v1/engineering-puzzle/goal-delta"]["surface_id"] == "engineering_puzzle_governance"
    assert classified_routes["/api/v1/export"]["surface_id"] == "data_export_lifecycle"
    assert classified_routes["/api/v1/export/sources"]["surface_id"] == "data_export_lifecycle"
    assert classified_routes["/api/v1/flags"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/flags/{flag_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/metrics"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/grafana/dashboard"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/prompts"]["surface_id"] == "prompt_template_lifecycle"
    assert classified_routes["/api/v1/prompts/render"]["surface_id"] == "prompt_template_lifecycle"
    assert classified_routes["/api/v1/rate-limit/status"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/rate-limits/{client_id}"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/replay/traces"]["surface_id"] == "replay_trace_read_models"
    assert classified_routes["/api/v1/schemas"]["surface_id"] == "schema_validation_registry"
    assert classified_routes["/api/v1/schemas/validate"]["surface_id"] == "schema_validation_registry"
    assert classified_routes["/api/v1/search"]["surface_id"] == "semantic_search_read_models"
    assert classified_routes["/api/v1/search/stats"]["surface_id"] == "semantic_search_read_models"
    assert classified_routes["/api/v1/sla"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/api/v1/sla/violations"]["surface_id"] == "operational_platform_read_models"
    assert classified_routes["/gateway/status"]["surface_id"] == "operational_platform_read_models"


def test_runtime_config_management_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    config_surface = surfaces["runtime_config_management"]
    witnesses = set(config_surface["runtime_witnesses"])

    assert config_surface["coverage_state"] == "witnessed"
    assert config_surface["request_proof"] == "request_proof"
    assert config_surface["action_proof"] == "action_proof"
    assert config_surface["audit"] == "audit_chain"
    assert "/api/v1/config/update" in config_surface["representative_paths"]
    assert "/api/v1/config/rollback" in config_surface["representative_paths"]
    assert "/api/v1/config/watcher" in config_surface["representative_paths"]
    assert "/api/v1/config/drift" in config_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/config.py" in config_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/config_reload.py" in config_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase207.py" in config_surface["evidence_files"]
    assert "mcoi/tests/test_config_drift.py" in config_surface["evidence_files"]
    assert "config_update_emits_event_and_audit" in witnesses
    assert "config_rollback_requires_known_version" in witnesses
    assert "config_watcher_errors_are_bounded" in witnesses
    assert "config_drift_secret_changes_are_critical" in witnesses
    assert route_records["/api/v1/config/update"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/config/update"]["surface_id"] == "runtime_config_management"
    assert route_records["/api/v1/config/drift"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/config/drift"]["surface_id"] == "runtime_config_management"
    assert closure_actions["classify_runtime_config_management_routes"]["status"] == "closed"


def test_webhooks_proof_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    webhooks_surface = surfaces["webhooks_proof_surface"]
    witnesses = set(webhooks_surface["runtime_witnesses"])

    assert webhooks_surface["coverage_state"] == "witnessed"
    assert webhooks_surface["request_proof"] == "request_proof"
    assert webhooks_surface["action_proof"] == "action_proof"
    assert webhooks_surface["audit"] == "audit_chain"
    assert "/api/v1/webhooks/subscribe" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks/deliveries" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks/retry/summary" in webhooks_surface["representative_paths"]
    assert "/api/v1/webhooks/retry/dead-letters" in webhooks_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in webhooks_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/webhook_retry.py" in webhooks_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase205.py" in webhooks_surface["evidence_files"]
    assert "mcoi/tests/test_webhook_system.py" in webhooks_surface["evidence_files"]
    assert "mcoi/tests/test_webhook_retry.py" in webhooks_surface["evidence_files"]
    assert "webhook_subscribe_records_audit" in witnesses
    assert "webhook_subscription_audited" in witnesses
    assert "webhook_subscription_mutation_receipt_emitted" in witnesses
    assert "webhook_delivery_history_is_bounded" in witnesses
    assert "webhook_delivery_mutation_receipts_exposed" in witnesses
    assert "webhook_delivery_history_bounded" in witnesses
    assert "webhook_delivery_queue_mutation_receipt_emitted" in witnesses
    assert "webhook_mutation_receipt_closes_effect_assurance" in witnesses
    assert "webhook_dead_letters_are_explicit" in witnesses
    assert "webhook_delivery_errors_are_sanitized" in witnesses
    assert route_records["/api/v1/webhooks/subscribe"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/webhooks/subscribe"]["surface_id"] == "webhooks_proof_surface"
    assert route_records["/api/v1/webhooks/retry/dead-letters"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/webhooks/retry/dead-letters"]["surface_id"] == "webhooks_proof_surface"
    assert closure_actions["classify_webhooks_routes"]["status"] == "closed"


def test_agent_adapter_protocol_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    agent_surface = surfaces["agent_adapter_protocol"]
    witnesses = set(agent_surface["runtime_witnesses"])

    assert agent_surface["coverage_state"] == "witnessed"
    assert agent_surface["request_proof"] == "request_proof"
    assert agent_surface["action_proof"] == "action_proof"
    assert "/api/v1/agent/register" in agent_surface["representative_paths"]
    assert "/api/v1/agent/action-request" in agent_surface["representative_paths"]
    assert "/api/v1/agent/restore" in agent_surface["representative_paths"]
    assert "/api/v1/agent/adapter/summary" in agent_surface["representative_paths"]
    assert "/api/v1/agents" in agent_surface["representative_paths"]
    assert "/api/v1/agents/{agent_id}/tasks" in agent_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/adapter.py" in agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/deps.py" in agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in agent_surface["evidence_files"]
    assert "mcoi/tests/test_agent_adapter_protocol.py" in agent_surface["evidence_files"]
    assert "agent_register_emits_governed_identity" in witnesses
    assert "agent_register_emits_audit_record" in witnesses
    assert "agent_action_request_runs_guard_chain" in witnesses
    assert "agent_checkpoint_restore_errors_are_bounded" in witnesses
    assert "agent_checkpoint_restore_roundtrip_governed" in witnesses
    assert "agent_adapter_summary_is_governed_read_model" in witnesses
    assert "agent_adapter_summary_bounded" in witnesses
    assert "builtin_agent_registry_read_models_governed" in witnesses
    assert closure_actions["classify_agent_adapter_protocol_routes"]["status"] == "closed"


def test_rbac_access_governance_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    rbac_surface = surfaces["rbac_access_governance"]
    witnesses = set(rbac_surface["runtime_witnesses"])

    assert rbac_surface["coverage_state"] == "witnessed"
    assert rbac_surface["request_proof"] == "request_proof"
    assert rbac_surface["action_proof"] == "action_proof"
    assert "/api/v1/rbac/identities" in rbac_surface["representative_paths"]
    assert "/api/v1/rbac/roles" in rbac_surface["representative_paths"]
    assert "/api/v1/rbac/bindings" in rbac_surface["representative_paths"]
    assert "/api/v1/rbac/summary" in rbac_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/rbac.py" in rbac_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/access_runtime.py" in rbac_surface["evidence_files"]
    assert "mcoi/tests/test_rbac_endpoints.py" in rbac_surface["evidence_files"]
    assert "rbac_identity_registration_governed" in witnesses
    assert "rbac_role_registration_governed" in witnesses
    assert "rbac_role_binding_governed" in witnesses
    assert "rbac_identity_creation_audited" in witnesses
    assert closure_actions["classify_rbac_access_governance_routes"]["status"] == "closed"


def test_remaining_declared_route_groups_are_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    expected_groups = (
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/bootstrap", "/api/v1/circuit-breaker", "/api/v1/llm/history"),
            "mcoi/mcoi_runtime/app/routers/llm/admin.py",
            "llm_history_window_bounded",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/dependencies", "/api/v1/dependencies/{name}/impact"),
            "mcoi/mcoi_runtime/app/routers/ops/dependencies.py",
            "dependency_impact_analysis_bounded",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/flags", "/api/v1/flags/{flag_id}"),
            "mcoi/mcoi_runtime/app/routers/ops/feature_flags.py",
            "missing_feature_flag_defaults_closed",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/metrics", "/api/v1/grafana/dashboard"),
            "mcoi/mcoi_runtime/app/routers/ops/metrics.py",
            "metrics_snapshot_bounded",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/rate-limit/status", "/api/v1/rate-limits/{client_id}"),
            "mcoi/mcoi_runtime/app/routers/ops/rate_limit.py",
            "rate_limit_read_model_non_mutating",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/api/v1/sla", "/api/v1/sla/violations"),
            "mcoi/mcoi_runtime/app/routers/data/sla.py",
            "sla_read_model_non_mutating",
        ),
        (
            "operational_platform_read_models",
            "classify_operational_platform_read_model_routes",
            ("/gateway/status",),
            "gateway/server.py",
            "gateway_status_governed",
        ),
        (
            "conversation_memory_lifecycle",
            "classify_conversation_memory_routes",
            ("/api/v1/conversation/message", "/api/v1/conversation/{conversation_id}", "/api/v1/conversations"),
            "mcoi/mcoi_runtime/app/routers/data/conversations.py",
            "missing_conversation_bounded_404",
        ),
        (
            "coordination_checkpoint_lifecycle",
            "classify_coordination_checkpoint_routes",
            ("/api/v1/coordination/checkpoint", "/api/v1/coordination/restore"),
            "mcoi/mcoi_runtime/app/routers/ops/coordination.py",
            "coordination_restore_missing_bounded",
        ),
        (
            "engineering_puzzle_governance",
            "classify_engineering_puzzle_routes",
            ("/api/v1/engineering-puzzle/candidates/judge", "/api/v1/engineering-puzzle/goal-delta"),
            "mcoi/mcoi_runtime/app/routers/engineering_puzzle.py",
            "engineering_candidate_judgment_governed",
        ),
        (
            "data_export_lifecycle",
            "classify_data_export_routes",
            ("/api/v1/export", "/api/v1/export/sources"),
            "mcoi/mcoi_runtime/app/routers/data/export.py",
            "data_export_format_validated",
        ),
        (
            "prompt_template_lifecycle",
            "classify_prompt_template_routes",
            ("/api/v1/prompts", "/api/v1/prompts/render"),
            "mcoi/mcoi_runtime/app/routers/data/prompts.py",
            "prompt_render_variables_validated",
        ),
        (
            "replay_trace_read_models",
            "classify_replay_trace_routes",
            ("/api/v1/replay/traces",),
            "mcoi/mcoi_runtime/app/routers/agent.py",
            "replay_trace_hash_projected",
        ),
        (
            "schema_validation_registry",
            "classify_schema_validation_routes",
            ("/api/v1/schemas", "/api/v1/schemas/validate"),
            "mcoi/mcoi_runtime/app/routers/data/schemas.py",
            "schema_validation_errors_explicit",
        ),
        (
            "semantic_search_read_models",
            "classify_semantic_search_routes",
            ("/api/v1/search", "/api/v1/search/stats"),
            "mcoi/mcoi_runtime/app/routers/data/search.py",
            "semantic_search_stats_bounded",
        ),
    )

    for surface_id, action_id, routes, evidence_file, witness in expected_groups:
        surface = surfaces[surface_id]
        witnesses = set(surface["runtime_witnesses"])

        assert surface["coverage_state"] == "witnessed"
        assert evidence_file in surface["evidence_files"]
        assert witness in witnesses
        assert closure_actions[action_id]["status"] == "closed"
        assert all(route in surface["representative_paths"] for route in routes)
        assert all(route_records[route]["surface_id"] == surface_id for route in routes)
        assert all(route_records[route]["coverage_state"] == "witnessed" for route in routes)


def test_finance_approval_packet_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    finance_surface = surfaces["finance_approval_packets"]
    witnesses = set(finance_surface["runtime_witnesses"])

    assert finance_surface["coverage_state"] == "witnessed"
    assert finance_surface["request_proof"] == "request_proof"
    assert finance_surface["action_proof"] == "action_proof"
    assert "/api/v1/finance/approval-packets" in finance_surface["representative_paths"]
    assert "/api/v1/finance/approval-packets/operator/read-model" in finance_surface["representative_paths"]
    assert "/api/v1/finance/approval-packets/{case_id}/approval" in finance_surface["representative_paths"]
    assert "/api/v1/finance/approval-packets/{case_id}/proof" in finance_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/finance_approval.py" in finance_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/finance_approval_packet.py" in finance_surface["evidence_files"]
    assert "mcoi/tests/test_finance_approval_packet.py" in finance_surface["evidence_files"]
    assert "mcoi/tests/test_finance_approval_router.py" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_payment_provider_binding_receipt.schema.json" in finance_surface["evidence_files"]
    assert "schemas/finance_approval_payment_closure_receipt.schema.json" in finance_surface["evidence_files"]
    assert "scripts/emit_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/produce_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "scripts/validate_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_emit_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_produce_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_payment_provider_binding_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_validate_finance_approval_payment_closure_receipt.py" in finance_surface["evidence_files"]
    assert "tests/test_finance_payment_provider_binding_examples.py" in finance_surface["evidence_files"]
    assert "examples/finance_payment_provider_binding_receipt_stripe.json" in finance_surface["evidence_files"]
    assert "examples/finance_payment_closure_receipt_stripe_bound.json" in finance_surface["evidence_files"]
    assert "finance_packet_policy_reasons_explicit" in witnesses
    assert "blocked_packet_emits_no_effect" in witnesses
    assert "approval_action_binds_approval_effect_and_closure_refs" in witnesses
    assert "payment_handoff_prepared_without_live_payment_claim" in witnesses
    assert "payment_receipt_and_ledger_reconciliation_required_for_payment_closure" in witnesses
    assert "payment_closure_receipt_validator_blocks_unbound_evidence" in witnesses
    assert "payment_closure_receipt_producer_emits_ready_sandbox_evidence" in witnesses
    assert "payment_provider_binding_receipt_redacts_credentials_and_scopes_provider" in witnesses
    assert "payment_closure_producer_consumes_provider_binding_receipt" in witnesses
    assert "payment_closure_validator_verifies_provider_binding_receipt_object" in witnesses
    assert "payment_closure_receipt_producer_requires_provider_binding_for_nonsandbox" in witnesses
    assert "payment_closure_example_evidence_validates_provider_binding_chain" in witnesses
    assert "packet_proof_requires_policy_evidence_and_closure_for_closed_states" in witnesses
    assert "operator_read_model_bounds_visible_packets_and_counts" in witnesses
    assert closure_actions["classify_finance_approval_packet_routes"]["status"] == "closed"


def test_federated_control_plane_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    federation_surface = surfaces["federated_control_plane"]
    witnesses = set(federation_surface["runtime_witnesses"])

    assert federation_surface["coverage_state"] == "witnessed"
    assert federation_surface["request_proof"] == "read_model"
    assert federation_surface["action_proof"] == "read_model"
    assert "/api/v1/federation/summary" in federation_surface["representative_paths"]
    assert "gateway/federated_control.py" in federation_surface["evidence_files"]
    assert "gateway/server.py" in federation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/federation.py" in federation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/federated_control_plane.py" in federation_surface["evidence_files"]
    assert "schemas/federated_control_snapshot.schema.json" in federation_surface["evidence_files"]
    assert "tests/test_gateway/test_federated_control.py" in federation_surface["evidence_files"]
    assert "signed_policy_metadata_only_sync" in witnesses
    assert "invalid_signature_denied_before_local_acceptance" in witnesses
    assert "policy_not_allowed_for_cluster_denied" in witnesses
    assert "unsynced_policy_denied_locally" in witnesses
    assert "tenant_region_mismatch_denied_locally" in witnesses
    assert "central_data_transfer_forbidden" in witnesses
    assert "federated_snapshot_schema_valid" in witnesses
    assert closure_actions["publish_federated_control_plane_read_model"]["status"] == "closed"


def test_gateway_runtime_witnesses_bind_closure_invariants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    gateway_surface = surfaces["gateway_capability_fabric"]
    witnesses = set(gateway_surface["runtime_witnesses"])

    assert gateway_surface["action_proof"] == "action_proof"
    assert "/capability-fabric/admission-audits" in gateway_surface["representative_paths"]
    assert "/capability-fabric/capsule-admissions" in gateway_surface["representative_paths"]
    assert "/capability-fabric/capsule-admission-receipts" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/closure" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/capability-admission" in gateway_surface["representative_paths"]
    assert "/commands/{command_id}/universal-action-proof" in gateway_surface["representative_paths"]
    assert "/operator/universal-actions/read-model" in gateway_surface["representative_paths"]
    assert "/operator/universal-actions" in gateway_surface["representative_paths"]
    assert "DomainCapsuleCompiler.compile" in gateway_surface["representative_paths"]
    assert "install_certified_capsule_with_handoff_evidence" in gateway_surface["representative_paths"]
    assert "gateway/capability_capsule_installer.py" in gateway_surface["evidence_files"]
    assert "gateway/command_spine.py" in gateway_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/governed_execution.py" in gateway_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/domain_capsule_compiler.py" in gateway_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_capsule_installer.py" in gateway_surface["evidence_files"]
    assert "tests/test_gateway/test_webhooks.py" in gateway_surface["evidence_files"]
    assert "tests/test_governed_capability_fabric.py" in gateway_surface["evidence_files"]
    assert "command_lifecycle_events_are_hash_linked" in witnesses
    assert "terminal_closure_requires_evidence_refs" in witnesses
    assert "successful_response_is_bound_to_response_evidence_closure" in witnesses
    assert "universal_action_proof_replays_from_command_events" in witnesses
    assert "operator_universal_action_read_model_filters_command_proofs" in witnesses
    assert "operator_universal_action_console_renders_replay_state" in witnesses
    assert "capability_admission_audits_filter_status" in witnesses
    assert "command_capability_admission_read_model_reports_accepted_witness" in witnesses
    assert "capsule_compiler_emits_certification_evidence_manifest" in witnesses
    assert "capsule_installer_stamps_admission_receipt" in witnesses
    assert "capsule_admission_operator_endpoint_lists_receipt" in witnesses
    assert "invalid_capsule_admission_preserves_registry_state" in witnesses
    assert "physical_capsule_admission_runs_promotion_preflight" in witnesses
    assert closure_actions["classify_gateway_capability_admission_routes"]["status"] == "closed"


def test_capability_worker_execution_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    worker_surface = surfaces["capability_worker_execution"]
    witnesses = set(worker_surface["runtime_witnesses"])

    assert worker_surface["coverage_state"] == "witnessed"
    assert worker_surface["request_proof"] == "request_proof"
    assert worker_surface["action_proof"] == "action_proof"
    assert worker_surface["audit"] == "audit_chain"
    assert "/capability/execute" in worker_surface["representative_paths"]
    assert "gateway/capability_worker.py" in worker_surface["evidence_files"]
    assert "gateway/capability_isolation.py" in worker_surface["evidence_files"]
    assert "gateway/capability_dispatch.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_worker.py" in worker_surface["evidence_files"]
    assert "signed_capability_request_required" in witnesses
    assert "response_signature_verified" in witnesses
    assert "input_hash_mismatch_rejected" in witnesses
    assert "intent_boundary_mismatch_rejected" in witnesses
    assert "non_isolated_boundary_rejected" in witnesses
    assert "local_smoke_stub_bound_to_local_environment" in witnesses
    assert "capability_worker_execution" in closure_actions["classify_gateway_capability_admission_routes"]["surfaces"]


def test_data_governance_controls_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    data_surface = surfaces["data_governance_controls"]
    witnesses = set(data_surface["runtime_witnesses"])

    assert data_surface["coverage_state"] == "witnessed"
    assert data_surface["request_proof"] == "request_proof"
    assert data_surface["action_proof"] == "action_proof"
    assert "/api/v1/data-governance/classify" in data_surface["representative_paths"]
    assert "/api/v1/data-governance/evaluate" in data_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/governance.py" in data_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/data_governance.py" in data_surface["evidence_files"]
    assert "mcoi/tests/test_data_governance_endpoints.py" in data_surface["evidence_files"]
    assert "data_governance_state_hash" in witnesses
    assert "data_governance_action_proof" in witnesses
    assert "tenant_visible_violation_read_model" in witnesses
    assert closure_actions["classify_data_governance_routes"]["status"] == "closed"


def test_compliance_evidence_exports_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    compliance_surface = surfaces["compliance_evidence_exports"]
    witnesses = set(compliance_surface["runtime_witnesses"])

    assert compliance_surface["coverage_state"] == "witnessed"
    assert compliance_surface["request_proof"] == "request_proof"
    assert compliance_surface["action_proof"] == "action_proof"
    assert "/api/v1/compliance/audit-package" in compliance_surface["representative_paths"]
    assert "/api/v1/compliance/summary" in compliance_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/compliance.py" in compliance_surface["evidence_files"]
    assert "mcoi/tests/test_compliance_export.py" in compliance_surface["evidence_files"]
    assert "scripts/compliance_alignment_matrix.py" in compliance_surface["evidence_files"]
    assert "compliance_package_hash" in witnesses
    assert "audit_chain_verification" in witnesses
    assert "self_audited_export_event" in witnesses
    assert closure_actions["classify_compliance_evidence_exports"]["status"] == "closed"


def test_tenant_governance_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    tenant_surface = surfaces["tenant_governance_lifecycle"]
    witnesses = set(tenant_surface["runtime_witnesses"])

    assert tenant_surface["coverage_state"] == "witnessed"
    assert tenant_surface["request_proof"] == "request_proof"
    assert tenant_surface["action_proof"] == "action_proof"
    assert "/api/v1/tenant/budget" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/{tenant_id}/budget" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/{tenant_id}/ledger" in tenant_surface["representative_paths"]
    assert "/api/v1/tenants" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/register" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/{tenant_id}/status" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant/gates" in tenant_surface["representative_paths"]
    assert "/api/v1/usage/{tenant_id}" in tenant_surface["representative_paths"]
    assert "/api/v1/tenant-isolation/audits" in tenant_surface["representative_paths"]
    assert "/api/v1/quotas/{tenant_id}" in tenant_surface["representative_paths"]
    assert "/api/v1/partitions" in tenant_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/tenant.py" in tenant_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/guards/budget.py" in tenant_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/guards/tenant_gating.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase202.py" in tenant_surface["evidence_files"]
    assert "mcoi/tests/test_governance_endpoints.py" in tenant_surface["evidence_files"]
    assert "tenant_budget_create_emits_action_proof" in witnesses
    assert "tenant_budget_create_records_audit" in witnesses
    assert "tenant_budget_read_models_scoped_by_tenant" in witnesses
    assert "tenant_ledger_queries_bounded" in witnesses
    assert "tenant_registry_lifecycle_errors_sanitized" in witnesses
    assert "tenant_register_emits_action_proof" in witnesses
    assert "tenant_status_update_emits_action_proof" in witnesses
    assert "tenant_gate_read_models_governed" in witnesses
    assert "tenant_usage_read_model_scoped" in witnesses
    assert "tenant_isolation_audits_bounded" in witnesses
    assert "tenant_quota_read_models_bounded" in witnesses
    assert "tenant_partition_read_model_bounded" in witnesses
    assert closure_actions["classify_tenant_governance_lifecycle_routes"]["status"] == "closed"


def test_runbook_learning_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runbook_surface = surfaces["runbook_learning_lifecycle"]
    witnesses = set(runbook_surface["runtime_witnesses"])

    assert runbook_surface["coverage_state"] == "witnessed"
    assert runbook_surface["request_proof"] == "request_proof"
    assert runbook_surface["action_proof"] == "action_proof"
    assert "/api/v1/runbooks" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/analyze" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/promote" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/approve" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/{runbook_id}/activate" in runbook_surface["representative_paths"]
    assert "/api/v1/runbooks/{runbook_id}/retire" in runbook_surface["representative_paths"]
    assert "/api/v1/mil-audit/admit-runbook" in runbook_surface["representative_paths"]
    assert "/api/v1/mil-audit/runbooks" in runbook_surface["representative_paths"]
    assert "/api/v1/mil-audit/runbooks/{runbook_id}" in runbook_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/runbooks.py" in runbook_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/mil_audit.py" in runbook_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/runbook_learning.py" in runbook_surface["evidence_files"]
    assert "mcoi/tests/test_mil_audit_router.py" in runbook_surface["evidence_files"]
    assert "mcoi/tests/test_runbook_learning.py" in runbook_surface["evidence_files"]
    assert "examples/mil_audit_runbook_operator_checklist.json" in runbook_surface["evidence_files"]
    assert "scripts/validate_mil_audit_runbook_operator_checklist.py" in runbook_surface["evidence_files"]
    assert "scripts/preflight_mil_audit_runbook_workflow.py" in runbook_surface["evidence_files"]
    assert "tests/test_validate_mil_audit_runbook_operator_checklist.py" in runbook_surface["evidence_files"]
    assert "tests/test_preflight_mil_audit_runbook_workflow.py" in runbook_surface["evidence_files"]
    assert "patterns_detected_from_audit_trail" in witnesses
    assert "promotion_requires_detected_pattern" in witnesses
    assert "approval_required_before_activation" in witnesses
    assert "retirement_requires_active_runbook" in witnesses
    assert "promote_and_approve_audit_records" in witnesses
    assert "mil_audit_replay_admits_runbook" in witnesses
    assert "mil_audit_operator_checklist_validated" in witnesses
    assert "mil_audit_runbook_preflight_ready" in witnesses
    assert "sanitized_runbook_error_details" in witnesses
    assert "runbook_pattern_read_models_bounded" in witnesses
    assert "runbook_responses_governed" in witnesses
    assert closure_actions["classify_runbook_learning_routes"]["status"] == "closed"


def test_software_outcome_learning_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    learning_surface = surfaces["software_outcome_learning"]
    witnesses = set(learning_surface["runtime_witnesses"])

    assert learning_surface["coverage_state"] == "witnessed"
    assert learning_surface["request_proof"] == "request_proof"
    assert learning_surface["action_proof"] == "action_proof"
    assert "mullu_software_change" in learning_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/mcp/server.py" in learning_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/software_learning.py" in learning_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/software_learning.py" in learning_surface["evidence_files"]
    assert "mcoi/tests/test_mcp_software_change.py" in learning_surface["evidence_files"]
    assert "mcoi/tests/test_software_learning.py" in learning_surface["evidence_files"]
    assert "software_learning_schema_default_enabled" in witnesses
    assert "passed_gates_yield_procedural_memory" in witnesses
    assert "failed_gates_yield_hashed_risk_memory" in witnesses
    assert "raw_logs_rejected_before_planning_use" in witnesses
    assert "rollback_failure_defers_learning" in witnesses
    assert "planning_projection_requires_admitted_matching_decision" in witnesses
    assert "software_learning_errors_are_bounded" in witnesses
    assert closure_actions["publish_software_outcome_learning_contract"]["status"] == "closed"


def test_authority_operator_controls_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    operator_surface = surfaces["authority_operator_controls"]
    witnesses = set(operator_surface["runtime_witnesses"])

    assert operator_surface["coverage_state"] == "witnessed"
    assert operator_surface["request_proof"] == "request_proof"
    assert operator_surface["action_proof"] == "action_proof"
    assert "/authority/operator" in operator_surface["representative_paths"]
    assert "/authority/operator-audit" in operator_surface["representative_paths"]
    assert "/authority/approval-chains/expire-overdue" in operator_surface["representative_paths"]
    assert "/authority/obligations/{obligation_id}/satisfy" in operator_surface["representative_paths"]
    assert "gateway/server.py" in operator_surface["evidence_files"]
    assert "gateway/authority_obligation_mesh.py" in operator_surface["evidence_files"]
    assert "scripts/collect_runtime_conformance.py" in operator_surface["evidence_files"]
    assert "tests/test_gateway/test_webhooks.py" in operator_surface["evidence_files"]
    assert "operator_access_guard" in witnesses
    assert "operator_audit_events" in witnesses
    assert "ownership_policy_read_models" in witnesses
    assert "approval_expiration_witness" in witnesses
    assert "obligation_satisfaction_escalation_witness" in witnesses
    assert closure_actions["classify_authority_operator_controls"]["status"] == "closed"


def test_authority_obligation_mesh_binds_command_authority_read_model() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    authority_surface = surfaces["authority_obligation_mesh"]
    witnesses = set(authority_surface["runtime_witnesses"])

    assert authority_surface["coverage_state"] == "witnessed"
    assert authority_surface["request_proof"] == "request_proof"
    assert authority_surface["action_proof"] == "action_proof"
    assert "/commands/{command_id}/authority" in authority_surface["representative_paths"]
    assert "gateway/authority_obligation_mesh.py" in authority_surface["evidence_files"]
    assert "tests/test_gateway/test_webhooks.py" in authority_surface["evidence_files"]
    assert "command_authority_read_model_bound_to_approval_chain" in witnesses
    assert "authority_obligation_mesh" in closure_actions["bound_authority_read_models_to_paginated_windows"]["surfaces"]


def test_audit_chain_api_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    audit_surface = surfaces["audit_chain_api"]
    witnesses = set(audit_surface["runtime_witnesses"])

    assert audit_surface["coverage_state"] == "witnessed"
    assert audit_surface["request_proof"] == "read_model"
    assert audit_surface["action_proof"] == "request_proof"
    assert "/api/v1/audit/verify" in audit_surface["representative_paths"]
    assert "/api/v1/audit/anchor/{anchor_id}/verify" in audit_surface["representative_paths"]
    assert "/api/v1/logs" in audit_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/audit.py" in audit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/trail.py" in audit_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/audit/anchor.py" in audit_surface["evidence_files"]
    assert "mcoi/tests/test_audit_trail.py" in audit_surface["evidence_files"]
    assert "mcoi/tests/test_v4_28_audit_checkpoint.py" in audit_surface["evidence_files"]
    assert "audit_chain_verify_endpoint" in witnesses
    assert "audit_anchor_checkpoint_created" in witnesses
    assert "audit_anchor_verification_endpoint" in witnesses
    assert "audit_logs_read_model_bounded" in witnesses
    assert closure_actions["classify_audit_chain_api"]["status"] == "closed"


def test_event_bus_operations_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    event_surface = surfaces["event_bus_operations"]
    witnesses = set(event_surface["runtime_witnesses"])

    assert event_surface["coverage_state"] == "witnessed"
    assert event_surface["request_proof"] == "request_proof"
    assert event_surface["action_proof"] == "action_proof"
    assert "/api/v1/events" in event_surface["representative_paths"]
    assert "/api/v1/events/publish" in event_surface["representative_paths"]
    assert "/api/v1/events/summary" in event_surface["representative_paths"]
    assert "/api/v1/events/store/summary" in event_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/audit.py" in event_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase206.py" in event_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase207.py" in event_surface["evidence_files"]
    assert "event_publish_hash_bound" in witnesses
    assert "event_history_filter_bounded" in witnesses
    assert "event_store_summary_governed" in witnesses
    assert "pipeline_completion_event_visible" in witnesses
    assert closure_actions["classify_event_bus_operations_routes"]["status"] == "closed"


def test_api_key_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    api_key_surface = surfaces["api_key_lifecycle"]
    witnesses = set(api_key_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert api_key_surface["coverage_state"] == "witnessed"
    assert api_key_surface["request_proof"] == "request_proof"
    assert api_key_surface["action_proof"] == "action_proof"
    assert "/api/v1/api-keys" in api_key_surface["representative_paths"]
    assert "/api/v1/api-keys/{key_id}" in api_key_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/api_keys.py" in api_key_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/auth/api_key.py" in api_key_surface["evidence_files"]
    assert "mcoi/tests/test_api_key_lifecycle.py" in api_key_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase216.py" in api_key_surface["evidence_files"]
    assert "api_key_create_rejects_wildcard_when_disabled" in witnesses
    assert "api_key_create_rejects_empty_scopes" in witnesses
    assert "api_key_revoke_missing_is_bounded" in witnesses
    assert "api_key_rotation_links_old_and_new_keys" in witnesses
    assert "api_key_expiration_and_stale_detection" in witnesses
    assert route_records["/api/v1/api-keys"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/api-keys"]["surface_id"] == "api_key_lifecycle"
    assert route_records["/api/v1/api-keys/{key_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/api-keys/{key_id}"]["surface_id"] == "api_key_lifecycle"
    assert closure_actions["classify_api_key_lifecycle_routes"]["status"] == "closed"


def test_conversation_memory_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    conversation_surface = surfaces["conversation_memory_lifecycle"]
    witnesses = set(conversation_surface["runtime_witnesses"])

    assert conversation_surface["coverage_state"] == "witnessed"
    assert conversation_surface["request_proof"] == "request_proof"
    assert conversation_surface["action_proof"] == "action_proof"
    assert conversation_surface["audit"] == "audit_chain"
    assert "/api/v1/conversation/message" in conversation_surface["representative_paths"]
    assert "/api/v1/conversation/{conversation_id}" in conversation_surface["representative_paths"]
    assert "/api/v1/conversations" in conversation_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/conversations.py" in conversation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/conversation_memory.py" in conversation_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase208.py" in conversation_surface["evidence_files"]
    assert "mcoi/tests/test_conversation_memory.py" in conversation_surface["evidence_files"]
    assert "conversation_message_append_increments_count" in witnesses
    assert "conversation_history_returns_messages_and_summary" in witnesses
    assert "conversation_store_tenant_filtering" in witnesses
    assert "conversation_memory_pruning_bounded" in witnesses
    assert route_records["/api/v1/conversation/message"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/conversation/message"]["surface_id"] == "conversation_memory_lifecycle"
    assert route_records["/api/v1/conversation/{conversation_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/conversation/{conversation_id}"]["surface_id"] == "conversation_memory_lifecycle"
    assert route_records["/api/v1/conversations"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/conversations"]["surface_id"] == "conversation_memory_lifecycle"
    assert closure_actions["classify_conversation_memory_routes"]["status"] == "closed"


def test_coordination_checkpoint_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    coordination_surface = surfaces["coordination_checkpoint_lifecycle"]
    witnesses = set(coordination_surface["runtime_witnesses"])

    assert coordination_surface["coverage_state"] == "witnessed"
    assert coordination_surface["request_proof"] == "request_proof"
    assert coordination_surface["action_proof"] == "action_proof"
    assert coordination_surface["audit"] == "audit_chain"
    assert "/api/v1/coordination/checkpoint" in coordination_surface["representative_paths"]
    assert "/api/v1/coordination/restore" in coordination_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/coordination.py" in coordination_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/coordination.py" in coordination_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/coordination_store.py" in coordination_surface["evidence_files"]
    assert "mcoi/tests/test_coordination_http_endpoints.py" in coordination_surface["evidence_files"]
    assert "mcoi/tests/test_coordination_engine_persistence.py" in coordination_surface["evidence_files"]
    assert "coordination_checkpoint_save_governed" in witnesses
    assert "coordination_restore_resumes_checkpoint" in witnesses
    assert "coordination_restore_missing_is_bounded" in witnesses
    assert "coordination_policy_drift_requires_review" in witnesses
    assert "coordination_store_path_traversal_rejected" in witnesses
    assert route_records["/api/v1/coordination/checkpoint"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/coordination/checkpoint"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert route_records["/api/v1/coordination/restore"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/coordination/restore"]["surface_id"] == "coordination_checkpoint_lifecycle"
    assert closure_actions["classify_coordination_checkpoint_routes"]["status"] == "closed"


def test_ops_proof_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    ops_surface = surfaces["ops_proof_surface"]
    witnesses = set(ops_surface["runtime_witnesses"])

    assert ops_surface["coverage_state"] == "witnessed"
    assert ops_surface["request_proof"] == "request_proof"
    assert ops_surface["action_proof"] == "action_proof"
    assert ops_surface["audit"] == "audit_chain"
    assert "/api/v1/ops/benchmarks" in ops_surface["representative_paths"]
    assert "/api/v1/ops/imports" in ops_surface["representative_paths"]
    assert "/api/v1/ops/proof-bridge" in ops_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/diagnostics.py" in ops_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/governance_bench.py" in ops_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/import_analyzer.py" in ops_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/proof_bridge.py" in ops_surface["evidence_files"]
    assert "mcoi/tests/test_governance_endpoints.py" in ops_surface["evidence_files"]
    assert "ops_benchmarks_return_governed_summary" in witnesses
    assert "ops_import_analysis_returns_dependency_summary" in witnesses
    assert "ops_proof_bridge_status_governed" in witnesses
    assert route_records["/api/v1/ops/benchmarks"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/ops/benchmarks"]["surface_id"] == "ops_proof_surface"
    assert route_records["/api/v1/ops/proof-bridge"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/ops/proof-bridge"]["surface_id"] == "ops_proof_surface"
    assert closure_actions["classify_ops_diagnostics_routes"]["status"] == "closed"


def test_gateway_runtime_witness_covers_orchestration_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    runtime_surface = surfaces["gateway_runtime_witness"]

    assert runtime_surface["coverage_state"] == "witnessed"
    assert "scripts/orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert ".github/workflows/gateway-publication.yml" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_publication_closure_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/deployment_orchestration_receipt_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_publication_readiness.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/gateway_publication_receipt_validation.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/latest_anchor_read_model.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/runtime_witness.schema.json" in runtime_surface["evidence_files"]
    assert "schemas/mullu_governance_protocol.manifest.json" in runtime_surface["evidence_files"]
    assert "tests/test_orchestrate_deployment_witness.py" in runtime_surface["evidence_files"]
    assert "tests/test_report_gateway_publication_readiness.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_gateway_publication_receipt.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_protocol_manifest.py" in runtime_surface["evidence_files"]
    assert "deployment_witness_orchestration_receipt" in runtime_surface["runtime_witnesses"]
    assert "latest_anchor_read_model_schema_valid" in runtime_surface["runtime_witnesses"]
    assert "runtime_witness_schema_valid" in runtime_surface["runtime_witnesses"]
    assert "deployment_publication_closure_validation_schema" in runtime_surface["runtime_witnesses"]
    assert "deployment_orchestration_validation_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_publication_readiness_schema" in runtime_surface["runtime_witnesses"]
    assert "gateway_publication_receipt_validation_schema" in runtime_surface["runtime_witnesses"]
    assert closure_actions["publish_deployment_orchestration_receipt_contract"]["status"] == "closed"


def test_gateway_runtime_witness_covers_publication_responsibility_debt() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    runtime_surface = surfaces["gateway_runtime_witness"]
    witnesses = set(runtime_surface["runtime_witnesses"])

    assert "schemas/deployment_witness.schema.json" in runtime_surface["evidence_files"]
    assert "scripts/validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "tests/test_validate_deployment_publication_closure.py" in runtime_surface["evidence_files"]
    assert "responsibility_debt_clear" in witnesses
    assert "runtime_responsibility_debt_clear" in witnesses
    assert "authority_responsibility_debt_clear" in witnesses
    assert "authority_overdue_approval_chain_count" in witnesses
    assert "authority_overdue_obligation_count" in witnesses
    assert "authority_escalated_obligation_count" in witnesses
    assert "authority_unowned_high_risk_capability_count" in witnesses


def test_production_evidence_plane_is_witnessed_and_schema_backed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_surface = surfaces["production_evidence_plane"]
    witnesses = set(evidence_surface["runtime_witnesses"])

    assert evidence_surface["coverage_state"] == "witnessed"
    assert evidence_surface["request_proof"] == "read_model"
    assert evidence_surface["action_proof"] == "read_model"
    assert evidence_surface["audit"] == "audit_chain"
    assert "/health" in evidence_surface["representative_paths"]
    assert "/deployment/witness" in evidence_surface["representative_paths"]
    assert "/capabilities/evidence" in evidence_surface["representative_paths"]
    assert "/audit/verify" in evidence_surface["representative_paths"]
    assert "/proof/verify" in evidence_surface["representative_paths"]
    assert "schemas/gateway_health.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/production_evidence_witness.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/capability_evidence_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/audit_verification_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "schemas/proof_verification_endpoint.schema.json" in evidence_surface["evidence_files"]
    assert "tests/test_gateway/test_production_evidence.py" in evidence_surface["evidence_files"]
    assert "tests/test_collect_deployment_witness.py" in evidence_surface["evidence_files"]
    assert "gateway_health_schema_valid" in witnesses
    assert "signed_production_evidence_witness" in witnesses
    assert "capability_evidence_schema_valid" in witnesses
    assert "audit_verification_schema_valid" in witnesses
    assert "proof_verification_schema_valid" in witnesses
    assert "deployment_collection_requires_production_evidence" in witnesses
    assert "live_physical_safety_evidence_derived_from_registry" in witnesses
    assert "live_physical_capability_requires_safety_evidence" in witnesses
    assert "sandbox_physical_capability_remains_non_production" in witnesses
    assert "missing_production_evidence_fails_closed" in witnesses
    assert closure_actions["publish_production_evidence_plane"]["status"] == "closed"
    assert "gateway_runtime_witness" in closure_actions["publish_production_evidence_plane"]["surfaces"]


def test_governed_session_request_envelope_is_covered() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    session_surface = surfaces["governed_session"]

    assert session_surface["request_proof"] == "request_proof"
    assert session_surface["action_proof"] == "action_proof"
    assert "GovernedSession.llm" in session_surface["representative_paths"]
    assert "mcoi/tests/test_governed_session.py" in session_surface["evidence_files"]


def test_gaps_have_closure_actions() -> None:
    matrix = _load_fixture()
    closure_surfaces = {
        surface_id
        for action in matrix["closure_actions"]
        for surface_id in action["surfaces"]
        if action["status"] == "open"
    }
    gap_surfaces = {
        surface["surface_id"]
        for surface in matrix["surfaces"]
        if "gap" in {surface["request_proof"], surface["action_proof"], surface["audit"]}
    }

    assert gap_surfaces <= closure_surfaces
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}

    assert closure_actions["bind_tool_arguments_to_capability_policy_receipts"]["status"] == "closed"
    assert closure_actions["normalize_gateway_request_receipt_envelopes"]["status"] == "closed"
    assert closure_actions["bound_authority_read_models_to_paginated_windows"]["status"] == "closed"
    assert surfaces["gateway_capability_fabric"]["request_proof"] == "request_proof"
    assert surfaces["tool_invocation"]["action_proof"] == "action_proof"
    assert "authority_obligation_mesh" in closure_actions["bound_authority_read_models_to_paginated_windows"]["surfaces"]
    assert all(action["surfaces"] for action in matrix["closure_actions"])


def test_closure_actions_reference_declared_surfaces() -> None:
    matrix = _load_fixture()
    declared_surfaces = {surface["surface_id"] for surface in matrix["surfaces"]}

    assert all(
        surface_id in declared_surfaces
        for action in matrix["closure_actions"]
        for surface_id in action["surfaces"]
    )
    assert {action["status"] for action in matrix["closure_actions"]} <= {"open", "closed"}


def test_evidence_files_exist() -> None:
    matrix = _load_fixture()
    evidence_files = {evidence_file for surface in matrix["surfaces"] for evidence_file in surface["evidence_files"]}

    assert "mcoi/mcoi_runtime/app/streaming.py" in evidence_files
    assert "schemas/streaming_budget_enforcement.schema.json" in evidence_files
    assert "schemas/lineage_query.schema.json" in evidence_files
    assert "mcoi/mcoi_runtime/app/routers/lineage.py" in evidence_files
    assert "docs/42_lineage_query_api.md" in evidence_files
    assert "gateway/server.py" in evidence_files
    assert all((REPO_ROOT / evidence_file).exists() for evidence_file in evidence_files)


def test_lineage_query_api_is_witnessed_read_model() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    lineage_surface = surfaces["lineage_query_api"]
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    assert lineage_surface["coverage_state"] == "witnessed"
    assert lineage_surface["request_proof"] == "read_model"
    assert lineage_surface["action_proof"] == "read_model"
    assert "/api/v1/lineage/command/{command_id}" in lineage_surface["representative_paths"]
    assert "/api/v1/lineage/artifact/{artifact_id}" in lineage_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/core/lineage_query.py" in lineage_surface["evidence_files"]
    assert "mcoi/tests/test_server_lineage.py" in lineage_surface["evidence_files"]
    assert "schemas/lineage_query.schema.json" in lineage_surface["evidence_files"]
    assert "docs/42_lineage_query_api.md" in lineage_surface["evidence_files"]
    assert closure_actions["implement_lineage_query_routes_and_schema"]["status"] == "closed"


def test_capability_plan_evidence_bundle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    plan_surface = surfaces["capability_plan_evidence_bundle"]
    conformance_surface = surfaces["runtime_conformance_attestation"]
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}

    assert plan_surface["coverage_state"] == "witnessed"
    assert plan_surface["request_proof"] == "request_proof"
    assert plan_surface["action_proof"] == "action_proof"
    assert "/capability-plans/{plan_id}/closure" in plan_surface["representative_paths"]
    assert "gateway/plan_ledger.py" in plan_surface["evidence_files"]
    assert "tests/test_gateway/test_plan.py" in plan_surface["evidence_files"]
    assert "plan_evidence_bundle" in plan_surface["runtime_witnesses"]
    assert "capability_plan_bundle_canary_passed" in conformance_surface["runtime_witnesses"]
    assert "physical_worker_canary_passed" in conformance_surface["runtime_witnesses"]
    assert "physical_worker_canary_artifact_hash_bound" in conformance_surface["runtime_witnesses"]
    assert "gateway/physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in conformance_surface["evidence_files"]
    assert "runtime_conformance_certificate_schema_valid" in conformance_surface["runtime_witnesses"]
    assert "runtime_conformance_collector_schema_valid" in conformance_surface["runtime_witnesses"]
    assert "proof_coverage_unclassified_routes_reported" in conformance_surface["runtime_witnesses"]
    assert closure_actions["publish_capability_plan_evidence_bundles"]["status"] == "closed"
    assert "runtime_conformance_attestation" in closure_actions["publish_capability_plan_evidence_bundles"]["surfaces"]


def test_proof_route_gap_triage_surface_preserves_route_gaps() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    triage_surface = surfaces["proof_route_gap_triage"]
    witnesses = set(triage_surface["runtime_witnesses"])

    assert triage_surface["coverage_state"] == "witnessed"
    assert triage_surface["request_proof"] == "read_model"
    assert triage_surface["action_proof"] == "read_model"
    assert "build_gap_triage_report" in triage_surface["representative_paths"]
    assert "scripts/proof_route_gap_triage.py" in triage_surface["evidence_files"]
    assert "tests/test_proof_route_gap_triage.py" in triage_surface["evidence_files"]
    assert "docs/70_proof_route_gap_triage.md" in triage_surface["evidence_files"]
    assert "unclassified_routes_grouped_by_family" in witnesses
    assert "route_gap_triage_binds_source_files_and_methods" in witnesses
    assert "closure_candidates_ranked_deterministically" in witnesses
    assert closure_actions["publish_proof_route_gap_triage_report"]["status"] == "closed"
    assert "runtime_conformance_attestation" in closure_actions["publish_proof_route_gap_triage_report"]["surfaces"]


def test_runtime_reflex_engine_surface_is_operator_gated_and_non_mutating() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    reflex_surface = surfaces["runtime_reflex_engine"]
    witnesses = set(reflex_surface["runtime_witnesses"])

    assert reflex_surface["coverage_state"] == "witnessed"
    assert reflex_surface["request_proof"] == "read_model"
    assert reflex_surface["action_proof"] == "request_proof"
    assert "/runtime/self/propose-upgrade" in reflex_surface["representative_paths"]
    assert "/runtime/self/promote" in reflex_surface["representative_paths"]
    assert "/runtime/self/deployment-witnesses" in reflex_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/contracts/reflex.py" in reflex_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/reflex.py" in reflex_surface["evidence_files"]
    assert "schemas/reflex_deployment_witness_envelope.schema.json" in reflex_surface["evidence_files"]
    assert "schemas/reflex_deployment_witness_validator_receipt.schema.json" in reflex_surface["evidence_files"]
    assert "scripts/emit_reflex_deployment_witness_validator_receipt.py" in reflex_surface["evidence_files"]
    assert "scripts/validate_reflex_deployment_witness.py" in reflex_surface["evidence_files"]
    assert "tests/test_gateway/test_reflex_endpoints.py" in reflex_surface["evidence_files"]
    assert "tests/test_emit_reflex_deployment_witness_validator_receipt.py" in reflex_surface["evidence_files"]
    assert "tests/test_validate_reflex_deployment_witness.py" in reflex_surface["evidence_files"]
    assert "operator_only_access" in witnesses
    assert "mutation_applied_false" in witnesses
    assert "certification_handoff_required" in witnesses
    assert "signed_reflex_witness" in witnesses
    assert "reflex_deployment_witness_schema" in witnesses
    assert "reflex_validator_receipt_schema" in witnesses
    assert "offline_reflex_witness_replay" in witnesses
    assert "reflex_validator_receipt_artifact" in witnesses
    assert closure_actions["publish_runtime_reflex_engine_read_models"]["status"] == "closed"


def test_governed_operational_intelligence_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    operational_surface = surfaces["governed_operational_intelligence"]
    witnesses = set(operational_surface["runtime_witnesses"])

    assert operational_surface["coverage_state"] == "witnessed"
    assert operational_surface["request_proof"] == "request_proof"
    assert operational_surface["action_proof"] == "action_proof"
    assert "WorldStateStore.add_entity" in operational_surface["representative_paths"]
    assert "GoalCompiler.compile" in operational_surface["representative_paths"]
    assert "CausalSimulator.simulate" in operational_surface["representative_paths"]
    assert "/api/v1/knowledge/entities" in operational_surface["representative_paths"]
    assert "/api/v1/knowledge/links" in operational_surface["representative_paths"]
    assert "/api/v1/knowledge/contradictions/unresolved" in operational_surface["representative_paths"]
    assert "/api/v1/simulate" in operational_surface["representative_paths"]
    assert "/api/v1/simulate/history" in operational_surface["representative_paths"]
    assert "gateway/world_state.py" in operational_surface["evidence_files"]
    assert "gateway/goal_compiler.py" in operational_surface["evidence_files"]
    assert "gateway/causal_simulator.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/knowledge.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/simulation.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/knowledge_graph.py" in operational_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/governance/policy/sandbox.py" in operational_surface["evidence_files"]
    assert "schemas/world_state.schema.json" in operational_surface["evidence_files"]
    assert "schemas/goal.schema.json" in operational_surface["evidence_files"]
    assert "schemas/simulation_receipt.schema.json" in operational_surface["evidence_files"]
    assert "mcoi/tests/test_knowledge_graph.py" in operational_surface["evidence_files"]
    assert "mcoi/tests/test_policy_sandbox.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_world_state.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_goal_compiler.py" in operational_surface["evidence_files"]
    assert "tests/test_gateway/test_causal_simulator.py" in operational_surface["evidence_files"]
    assert "world_assertions_require_source_evidence" in witnesses
    assert "knowledge_entity_routes_governed" in witnesses
    assert "knowledge_link_routes_governed" in witnesses
    assert "knowledge_contradiction_routes_governed" in witnesses
    assert "knowledge_summary_route_bounded" in witnesses
    assert "policy_simulation_routes_governed" in witnesses
    assert "policy_simulation_history_summary_bounded" in witnesses
    assert "goal_plan_certificate_hash_bound" in witnesses
    assert "simulation_receipt_schema_valid" in witnesses
    assert "open_world_contradictions_block_execution" in witnesses
    assert "high_risk_controls_projected_before_execution" in witnesses
    assert closure_actions["publish_governed_operational_intelligence_witnesses"]["status"] == "closed"
    assert closure_actions["classify_world_state_knowledge_routes"]["status"] == "closed"
    assert closure_actions["classify_policy_simulation_routes"]["status"] == "closed"


def test_capability_forge_surface_is_candidate_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    forge_surface = surfaces["capability_forge"]
    witnesses = set(forge_surface["runtime_witnesses"])

    assert forge_surface["coverage_state"] == "witnessed"
    assert forge_surface["request_proof"] == "request_proof"
    assert forge_surface["action_proof"] == "action_proof"
    assert "CapabilityForge.create_candidate" in forge_surface["representative_paths"]
    assert "CapabilityForge.validate" in forge_surface["representative_paths"]
    assert "CapabilityForge.build_certification_handoff" in forge_surface["representative_paths"]
    assert "install_certification_handoff_evidence" in forge_surface["representative_paths"]
    assert "install_certification_handoff_evidence_batch" in forge_surface["representative_paths"]
    assert "gateway/capability_forge.py" in forge_surface["evidence_files"]
    assert "schemas/capability_candidate.schema.json" in forge_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_forge.py" in forge_surface["evidence_files"]
    assert "candidate_promotion_blocked" in witnesses
    assert "candidate_schema_valid" in witnesses
    assert "candidate_certification_handoff_emits_maturity_bundle" in witnesses
    assert "certification_handoff_installs_evidence_without_maturity_claim" in witnesses
    assert "certification_handoff_batch_preserves_capsule_admission_gate" in witnesses
    assert "physical_candidate_declares_live_safety_evidence_requirements" in witnesses
    assert "physical_handoff_installs_live_safety_evidence" in witnesses
    assert "high_risk_approval_policy_required" in witnesses
    assert "effect_bearing_candidate_requires_sandbox" in witnesses
    assert "effect_bearing_candidate_requires_recovery_path" in witnesses
    assert closure_actions["publish_capability_forge_candidate_contract"]["status"] == "closed"


def test_capability_maturity_surface_blocks_readiness_overclaims() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    maturity_surface = surfaces["capability_maturity_assessment"]
    witnesses = set(maturity_surface["runtime_witnesses"])

    assert maturity_surface["coverage_state"] == "witnessed"
    assert maturity_surface["request_proof"] == "request_proof"
    assert maturity_surface["action_proof"] == "action_proof"
    assert "CapabilityMaturityEvidenceSynthesizer.materialize_extension" in maturity_surface["representative_paths"]
    assert "CapabilityMaturityAssessor.assess" in maturity_surface["representative_paths"]
    assert "CapabilityRegistryMaturityProjector.decorate_read_model" in maturity_surface["representative_paths"]
    assert "MaturityProjectingCapabilityAdmissionGate.read_model" in maturity_surface["representative_paths"]
    assert "capabilities/connector/capability_pack.json" in maturity_surface["evidence_files"]
    assert "capabilities/financial/capability_pack.json" in maturity_surface["evidence_files"]
    assert "docs/39_governed_capability_fabric.md" in maturity_surface["evidence_files"]
    assert "gateway/capability_fabric.py" in maturity_surface["evidence_files"]
    assert "gateway/capability_maturity.py" in maturity_surface["evidence_files"]
    assert "gateway/operator_capability_console.py" in maturity_surface["evidence_files"]
    assert "schemas/capability_maturity.schema.json" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_fabric.py" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_maturity.py" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_operator_capability_console.py" in maturity_surface["evidence_files"]
    assert "certification_evidence_synthesizes_maturity_extension" in witnesses
    assert "maturity_derived_from_evidence" in witnesses
    assert "registry_read_model_exposes_maturity" in witnesses
    assert "default_pack_C6_examples_projected" in witnesses
    assert "effect_bearing_production_requires_live_write" in witnesses
    assert "production_requires_worker_deployment_recovery" in witnesses
    assert "autonomy_requires_C7_controls" in witnesses
    assert "capability_maturity_schema_valid" in witnesses
    assert closure_actions["publish_capability_maturity_assessment_contract"]["status"] == "closed"


def test_capability_manifest_registry_surface_admits_governed_manifests() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    manifest_surface = surfaces["capability_manifest_registry"]
    witnesses = set(manifest_surface["runtime_witnesses"])

    assert manifest_surface["coverage_state"] == "witnessed"
    assert manifest_surface["request_proof"] == "request_proof"
    assert manifest_surface["action_proof"] == "action_proof"
    assert "CapabilityManifestRegistry.admit_path" in manifest_surface["representative_paths"]
    assert "CapabilityManifestAdmission" in manifest_surface["representative_paths"]
    assert "build_software_dev_capability_manifest_registry" in manifest_surface["representative_paths"]
    assert "gateway/capability_fabric.py" in manifest_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/capability_manifest.py" in manifest_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/capability_manifest_registry.py" in manifest_surface["evidence_files"]
    assert "schemas/software_dev/capability_manifest.schema.json" in manifest_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_fabric.py" in manifest_surface["evidence_files"]
    assert "tests/test_software_dev_capability_manifest_registry.py" in manifest_surface["evidence_files"]
    assert "capability_manifest_schema_valid" in witnesses
    assert "software_dev_manifests_admit_locally" in witnesses
    assert "effect_manifest_requires_sandbox_rollback" in witnesses
    assert "production_hot_reload_denied_for_effect_manifest" in witnesses
    assert "fabric_projects_local_manifest_registry" in witnesses
    assert "fabric_rejects_production_hot_reload_manifest_registry" in witnesses
    assert closure_actions["publish_capability_manifest_registry_contract"]["status"] == "closed"


def test_networked_worker_mesh_surface_requires_non_terminal_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    worker_surface = surfaces["networked_worker_mesh"]
    witnesses = set(worker_surface["runtime_witnesses"])

    assert worker_surface["coverage_state"] == "witnessed"
    assert worker_surface["request_proof"] == "request_proof"
    assert worker_surface["action_proof"] == "action_proof"
    assert "NetworkedWorkerMesh.register_worker" in worker_surface["representative_paths"]
    assert "NetworkedWorkerMesh.dispatch" in worker_surface["representative_paths"]
    assert "NetworkedWorkerMesh.read_model" in worker_surface["representative_paths"]
    assert "SandboxedCodeWorker.execute_command" in worker_surface["representative_paths"]
    assert "CodeWorkerLease" in worker_surface["representative_paths"]
    assert "CodeWorkerReceipt" in worker_surface["representative_paths"]
    assert "gateway/physical_action_boundary.py" in worker_surface["evidence_files"]
    assert "gateway/physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "gateway/worker_mesh.py" in worker_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/code_worker.py" in worker_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/workers/code_worker.py" in worker_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "schemas/physical_action_receipt.schema.json" in worker_surface["evidence_files"]
    assert "schemas/worker_mesh.schema.json" in worker_surface["evidence_files"]
    assert "tests/test_code_worker.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_action_boundary.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "tests/test_gateway/test_worker_mesh.py" in worker_surface["evidence_files"]
    assert "tests/test_produce_physical_worker_canary.py" in worker_surface["evidence_files"]
    assert "active_lease_required" in witnesses
    assert "tenant_capability_operation_budget_checked" in witnesses
    assert "forbidden_operations_override_allowed" in witnesses
    assert "code_worker_exact_lease_command_required" in witnesses
    assert "code_worker_blocks_network_shell_and_risky_git" in witnesses
    assert "code_worker_receipt_binds_sandbox_evidence" in witnesses
    assert "physical_action_receipt_required_for_physical_workers" in witnesses
    assert "physical_worker_canary_blocks_without_receipt" in witnesses
    assert "physical_worker_canary_passed" in witnesses
    assert "physical_worker_canary_uses_sandbox_handler" in witnesses
    assert "worker_evidence_refs_required" in witnesses
    assert "worker_receipt_not_terminal_closure" in witnesses
    assert "worker_mesh_schema_valid" in witnesses
    assert closure_actions["publish_networked_worker_mesh_contract"]["status"] == "closed"


def test_software_dev_capability_pack_surface_requires_explicit_admission() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    software_surface = surfaces["software_dev_capability_pack"]
    witnesses = set(software_surface["runtime_witnesses"])

    assert software_surface["coverage_state"] == "witnessed"
    assert software_surface["request_proof"] == "request_proof"
    assert software_surface["action_proof"] == "action_proof"
    assert "build_software_dev_capability_admission_gate" in software_surface["representative_paths"]
    assert "software_dev.repo_map.read" in software_surface["representative_paths"]
    assert "software_dev.change.run" in software_surface["representative_paths"]
    assert "software_dev.pr_candidate.prepare" in software_surface["representative_paths"]
    assert "capsules/software_dev.json" in software_surface["evidence_files"]
    assert "capabilities/software_dev/capability_pack.json" in software_surface["evidence_files"]
    assert "gateway/capability_fabric.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_intelligence.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_context_builder.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/software_gate_planner.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/workers/code_worker.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/app_builder/codegen_pipeline.py" in software_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/app_builder/pr_candidate.py" in software_surface["evidence_files"]
    assert "schemas/software_dev/app_task_graph.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/app_task_graph.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/change_run.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/code_context_bundle.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/context_bundle.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/gate_plan.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/pr_candidate.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/pr_candidate.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/repo_map.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/repo_map_read.input.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/software_change_receipt.output.schema.json" in software_surface["evidence_files"]
    assert "schemas/software_dev/software_gate_plan.output.schema.json" in software_surface["evidence_files"]
    assert "tests/test_software_dev_capability_pack.py" in software_surface["evidence_files"]
    assert "software_dev_pack_fixture_not_default_loaded" in witnesses
    assert "software_dev_capability_entries_schema_valid" in witnesses
    assert "software_dev_input_schema_refs_materialized" in witnesses
    assert "software_dev_input_schemas_reject_boundary_violations" in witnesses
    assert "software_dev_output_schema_refs_materialized" in witnesses
    assert "software_dev_output_schemas_reject_effect_overclaims" in witnesses
    assert "software_dev_named_loader_installs_only_software_dev_domain" in witnesses
    assert "software_dev_gate_projects_manifest_registry" in witnesses
    assert "software_dev_capsule_refs_match_pack_capabilities" in witnesses
    assert "software_dev_direct_deployment_capability_absent" in witnesses
    assert "software_dev_read_only_records_non_mutating" in witnesses
    assert "software_dev_effectful_records_require_sandbox_approval" in witnesses
    assert "software_dev_pr_candidate_blocks_git_push" in witnesses
    assert "software_dev_production_ready_overclaim_rejected" in witnesses
    assert closure_actions["publish_software_dev_capability_pack_contract"]["status"] == "closed"


def test_agent_identity_surface_binds_owner_tenant_and_scope() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    identity_surface = surfaces["agent_identity"]
    witnesses = set(identity_surface["runtime_witnesses"])

    assert identity_surface["coverage_state"] == "witnessed"
    assert identity_surface["request_proof"] == "request_proof"
    assert identity_surface["action_proof"] == "action_proof"
    assert "AgentIdentityRegistry.register" in identity_surface["representative_paths"]
    assert "AgentIdentityRegistry.evaluate" in identity_surface["representative_paths"]
    assert "gateway/agent_identity.py" in identity_surface["evidence_files"]
    assert "schemas/agent_identity.schema.json" in identity_surface["evidence_files"]
    assert "tests/test_gateway/test_agent_identity.py" in identity_surface["evidence_files"]
    assert "owner_tenant_identity_required" in witnesses
    assert "self_approval_forbidden" in witnesses
    assert "policy_mutation_forbidden" in witnesses
    assert "delegation_requires_lease" in witnesses
    assert "agent_budget_enforced" in witnesses
    assert "agent_identity_schema_valid" in witnesses
    assert closure_actions["publish_agent_identity_contract"]["status"] == "closed"


def test_claim_verification_surface_gates_execution_admission() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    claim_surface = surfaces["claim_verification"]
    witnesses = set(claim_surface["runtime_witnesses"])

    assert claim_surface["coverage_state"] == "witnessed"
    assert claim_surface["request_proof"] == "request_proof"
    assert claim_surface["action_proof"] == "action_proof"
    assert "ClaimVerificationEngine.verify" in claim_surface["representative_paths"]
    assert "gateway/claim_verification.py" in claim_surface["evidence_files"]
    assert "schemas/claim_verification_report.schema.json" in claim_surface["evidence_files"]
    assert "tests/test_gateway/test_claim_verification.py" in claim_surface["evidence_files"]
    assert "source_evidence_required" in witnesses
    assert "contradictions_block_execution" in witnesses
    assert "stale_claims_block_execution" in witnesses
    assert "high_risk_requires_independent_support" in witnesses
    assert "claim_verification_schema_valid" in witnesses
    assert closure_actions["publish_claim_verification_report_contract"]["status"] == "closed"


def test_governed_connector_framework_surface_gates_invocation_lifecycle() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    connector_surface = surfaces["governed_connector_framework"]
    witnesses = set(connector_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert connector_surface["coverage_state"] == "witnessed"
    assert connector_surface["request_proof"] == "request_proof"
    assert connector_surface["action_proof"] == "action_proof"
    assert "/api/v1/connectors/register" in connector_surface["representative_paths"]
    assert "/api/v1/connectors/invoke" in connector_surface["representative_paths"]
    assert "/api/v1/connectors/{connector_id}/disable" in connector_surface["representative_paths"]
    assert "/api/v1/connectors/{connector_id}/enable" in connector_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/connectors.py" in connector_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/connector_framework.py" in connector_surface["evidence_files"]
    assert "mcoi/tests/test_connector_framework.py" in connector_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase217.py" in connector_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase218.py" in connector_surface["evidence_files"]
    assert "connector_registration_typed" in witnesses
    assert "connector_invocation_guard_chain_checked" in witnesses
    assert "connector_lifecycle_disable_enable_bounded" in witnesses
    assert "connector_history_summary_bounded" in witnesses
    assert "connector_errors_sanitized" in witnesses
    assert "connector_invocation_audited" in witnesses
    assert route_records["/api/v1/connectors/register"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/connectors/register"]["surface_id"] == "governed_connector_framework"
    assert route_records["/api/v1/connectors/invoke"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/connectors/invoke"]["surface_id"] == "governed_connector_framework"
    assert closure_actions["classify_governed_connector_routes"]["status"] == "closed"


def test_governed_background_scheduler_surface_gates_job_lifecycle() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    scheduler_surface = surfaces["governed_background_scheduler"]
    witnesses = set(scheduler_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert scheduler_surface["coverage_state"] == "witnessed"
    assert scheduler_surface["request_proof"] == "request_proof"
    assert scheduler_surface["action_proof"] == "action_proof"
    assert "/api/v1/scheduler/jobs" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/execute" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/jobs/{job_id}" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/jobs/{job_id}/disable" in scheduler_surface["representative_paths"]
    assert "/api/v1/scheduler/jobs/{job_id}/enable" in scheduler_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/scheduler.py" in scheduler_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/scheduler.py" in scheduler_surface["evidence_files"]
    assert "mcoi/tests/test_scheduler.py" in scheduler_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase217.py" in scheduler_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase218.py" in scheduler_surface["evidence_files"]
    assert "scheduler_job_registration_typed" in witnesses
    assert "scheduler_execute_guard_chain_checked" in witnesses
    assert "scheduler_lifecycle_controls_bounded" in witnesses
    assert "scheduler_history_summary_bounded" in witnesses
    assert "scheduler_errors_sanitized" in witnesses
    assert "scheduler_execution_audited" in witnesses
    assert route_records["/api/v1/scheduler/jobs"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/scheduler/jobs"]["surface_id"] == "governed_background_scheduler"
    assert route_records["/api/v1/scheduler/execute"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/scheduler/execute"]["surface_id"] == "governed_background_scheduler"
    assert closure_actions["classify_governed_scheduler_routes"]["status"] == "closed"


def test_multi_agent_coordination_runtime_surface_tracks_cooperation_lifecycle() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    multi_agent_surface = surfaces["multi_agent_coordination_runtime"]
    witnesses = set(multi_agent_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert multi_agent_surface["coverage_state"] == "witnessed"
    assert multi_agent_surface["request_proof"] == "request_proof"
    assert multi_agent_surface["action_proof"] == "action_proof"
    assert "/api/v1/multi-agent/delegate" in multi_agent_surface["representative_paths"]
    assert "/api/v1/multi-agent/delegate/resolve" in multi_agent_surface["representative_paths"]
    assert "/api/v1/multi-agent/handoff" in multi_agent_surface["representative_paths"]
    assert "/api/v1/multi-agent/conflicts/unresolved" in multi_agent_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/multi_agent.py" in multi_agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/coordination.py" in multi_agent_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/coordination.py" in multi_agent_surface["evidence_files"]
    assert "mcoi/tests/test_multi_agent_runtime.py" in multi_agent_surface["evidence_files"]
    assert "multi_agent_delegation_tracked" in witnesses
    assert "multi_agent_handoff_preserves_context" in witnesses
    assert "multi_agent_conflict_strategy_typed" in witnesses
    assert "multi_agent_errors_sanitized" in witnesses
    assert route_records["/api/v1/multi-agent/delegate"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/multi-agent/delegate"]["surface_id"] == "multi_agent_coordination_runtime"
    assert route_records["/api/v1/multi-agent/summary"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/multi-agent/summary"]["surface_id"] == "multi_agent_coordination_runtime"
    assert closure_actions["classify_multi_agent_coordination_routes"]["status"] == "closed"


def test_task_queue_lifecycle_surface_tracks_priority_processing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    queue_surface = surfaces["task_queue_lifecycle"]
    witnesses = set(queue_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert queue_surface["coverage_state"] == "witnessed"
    assert queue_surface["request_proof"] == "request_proof"
    assert queue_surface["action_proof"] == "action_proof"
    assert "/api/v1/queue/submit" in queue_surface["representative_paths"]
    assert "/api/v1/queue/process" in queue_surface["representative_paths"]
    assert "/api/v1/queue/status" in queue_surface["representative_paths"]
    assert "/api/v1/queue/result/{task_id}" in queue_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in queue_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/task_queue.py" in queue_surface["evidence_files"]
    assert "mcoi/tests/test_task_queue.py" in queue_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase215.py" in queue_surface["evidence_files"]
    assert "task_queue_priority_order" in witnesses
    assert "task_queue_depth_bounded" in witnesses
    assert "task_queue_empty_process_bounded" in witnesses
    assert "task_queue_missing_result_bounded" in witnesses
    assert "task_queue_errors_sanitized" in witnesses
    assert route_records["/api/v1/queue/submit"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/queue/submit"]["surface_id"] == "task_queue_lifecycle"
    assert route_records["/api/v1/queue/result/{task_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/queue/result/{task_id}"]["surface_id"] == "task_queue_lifecycle"
    assert closure_actions["classify_task_queue_lifecycle_routes"]["status"] == "closed"


def test_trace_observability_surface_exposes_read_only_models() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    trace_surface = surfaces["trace_observability_read_models"]
    witnesses = set(trace_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert trace_surface["coverage_state"] == "witnessed"
    assert trace_surface["request_proof"] == "read_model"
    assert trace_surface["action_proof"] == "read_model"
    assert "/api/v1/traces" in trace_surface["representative_paths"]
    assert "/api/v1/traces/slow" in trace_surface["representative_paths"]
    assert "/api/v1/traces/summary" in trace_surface["representative_paths"]
    assert "/api/v1/traces/{trace_id}" in trace_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in trace_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/summaries.py" in trace_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/request_tracing.py" in trace_surface["evidence_files"]
    assert "mcoi/tests/test_request_tracing.py" in trace_surface["evidence_files"]
    assert "request_trace_summary_bounded" in witnesses
    assert "missing_trace_returns_governed_404" in witnesses
    assert "slow_trace_projection_bounded" in witnesses
    assert "otel_trace_summary_bounded" in witnesses
    assert route_records["/api/v1/traces"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/traces"]["surface_id"] == "trace_observability_read_models"
    assert route_records["/api/v1/traces/summary"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/traces/summary"]["surface_id"] == "trace_observability_read_models"
    assert closure_actions["classify_trace_observability_routes"]["status"] == "closed"


def test_agent_memory_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    memory_surface = surfaces["agent_memory_lifecycle"]
    witnesses = set(memory_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert memory_surface["coverage_state"] == "witnessed"
    assert memory_surface["request_proof"] == "request_proof"
    assert memory_surface["action_proof"] == "action_proof"
    assert "/api/v1/memory/store" in memory_surface["representative_paths"]
    assert "/api/v1/memory/search" in memory_surface["representative_paths"]
    assert "/api/v1/memory/summary" in memory_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in memory_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_memory.py" in memory_surface["evidence_files"]
    assert "mcoi/tests/test_agent_memory.py" in memory_surface["evidence_files"]
    assert "agent_memory_store_bounded" in witnesses
    assert "agent_memory_search_relevance_scored" in witnesses
    assert "agent_memory_tenant_isolation" in witnesses
    assert "agent_memory_capacity_eviction" in witnesses
    assert route_records["/api/v1/memory/store"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/memory/store"]["surface_id"] == "agent_memory_lifecycle"
    assert route_records["/api/v1/memory/summary"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/memory/summary"]["surface_id"] == "agent_memory_lifecycle"
    assert closure_actions["classify_agent_memory_lifecycle_routes"]["status"] == "closed"


def test_governance_explanation_lifecycle_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    explanation_surface = surfaces["governance_explanation_lifecycle"]
    witnesses = set(explanation_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert explanation_surface["coverage_state"] == "witnessed"
    assert explanation_surface["request_proof"] == "request_proof"
    assert explanation_surface["action_proof"] == "action_proof"
    assert "/api/v1/explain/action" in explanation_surface["representative_paths"]
    assert "/api/v1/explain/audit/{entry_index}" in explanation_surface["representative_paths"]
    assert "/api/v1/explain/summary" in explanation_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/explain.py" in explanation_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/explanation_engine.py" in explanation_surface["evidence_files"]
    assert "mcoi/tests/test_explanation_engine.py" in explanation_surface["evidence_files"]
    assert "explain_action_guard_chain_path_reported" in witnesses
    assert "explain_action_returns_explanation_id" in witnesses
    assert "explain_audit_entry_allowed_and_denied" in witnesses
    assert "explanation_cache_bounded" in witnesses
    assert "explain_summary_endpoint_governed" in witnesses
    assert route_records["/api/v1/explain/action"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/explain/action"]["surface_id"] == "governance_explanation_lifecycle"
    assert route_records["/api/v1/explain/summary"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/explain/summary"]["surface_id"] == "governance_explanation_lifecycle"
    assert closure_actions["classify_governance_explanation_lifecycle_routes"]["status"] == "closed"


def test_tool_registry_read_model_surface_keeps_invocation_separate() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    tool_surface = surfaces["tool_registry_read_models"]
    witnesses = set(tool_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert tool_surface["coverage_state"] == "witnessed"
    assert tool_surface["request_proof"] == "read_model"
    assert tool_surface["action_proof"] == "read_model"
    assert "/api/v1/tools" in tool_surface["representative_paths"]
    assert "/api/v1/tools/history" in tool_surface["representative_paths"]
    assert "/api/v1/tools/llm-format" in tool_surface["representative_paths"]
    assert "/api/v1/tools/invoke" not in tool_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/tools.py" in tool_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/tool_use.py" in tool_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase212.py" in tool_surface["evidence_files"]
    assert "tool_registry_list_returns_registered_tools" in witnesses
    assert "tool_llm_format_exports_input_schema" in witnesses
    assert "tool_history_returns_bounded_summary" in witnesses
    assert "tool_invoke_separate_action_proof_surface" in witnesses
    assert route_records["/api/v1/tools"]["surface_id"] == "tool_registry_read_models"
    assert route_records["/api/v1/tools/history"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/tools/llm-format"]["surface_id"] == "tool_registry_read_models"
    assert route_records["/api/v1/tools/invoke"]["surface_id"] == "tool_invocation"
    assert closure_actions["classify_tool_registry_read_model_routes"]["status"] == "closed"


def test_structured_output_validation_surface_is_witnessed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    output_surface = surfaces["structured_output_validation"]
    witnesses = set(output_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert output_surface["coverage_state"] == "witnessed"
    assert output_surface["request_proof"] == "request_proof"
    assert output_surface["action_proof"] == "action_proof"
    assert "/api/v1/output/parse" in output_surface["representative_paths"]
    assert "/api/v1/output/schemas" in output_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/output.py" in output_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/structured_output.py" in output_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase212.py" in output_surface["evidence_files"]
    assert "mcoi/tests/test_structured_output.py" in output_surface["evidence_files"]
    assert "structured_output_parse_valid_json" in witnesses
    assert "structured_output_parse_invalid_json" in witnesses
    assert "structured_output_parse_unknown_schema_bounded" in witnesses
    assert "structured_output_schema_registration_validated" in witnesses
    assert "structured_output_endpoint_parse_valid_and_invalid" in witnesses
    assert route_records["/api/v1/output/parse"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/output/parse"]["surface_id"] == "structured_output_validation"
    assert route_records["/api/v1/output/schemas"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/output/schemas"]["surface_id"] == "structured_output_validation"
    assert closure_actions["classify_structured_output_validation_routes"]["status"] == "closed"


def test_rate_limit_read_model_surface_exposes_bounded_status_and_headers() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    rate_surface = surfaces["rate_limit_read_models"]
    witnesses = set(rate_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert rate_surface["coverage_state"] == "witnessed"
    assert rate_surface["request_proof"] == "read_model"
    assert rate_surface["action_proof"] == "read_model"
    assert "/api/v1/rate-limit/status" in rate_surface["representative_paths"]
    assert "/api/v1/rate-limits/{client_id}" in rate_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/rate_limit.py" in rate_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/rate_limit_headers.py" in rate_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/rate_limit_middleware.py" in rate_surface["evidence_files"]
    assert "mcoi/tests/test_rate_limiter.py" in rate_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase202.py" in rate_surface["evidence_files"]
    assert "mcoi/tests/test_rate_limit_headers.py" in rate_surface["evidence_files"]
    assert "rate_limit_status_reports_allowed_and_active_buckets" in witnesses
    assert "rate_limit_headers_project_limit_remaining_reset" in witnesses
    assert "rate_limit_header_peek_does_not_consume" in witnesses
    assert "atomic_rate_limit_store_bounds_concurrent_consumption" in witnesses
    assert route_records["/api/v1/rate-limit/status"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/rate-limit/status"]["surface_id"] == "rate_limit_read_models"
    assert route_records["/api/v1/rate-limits/{client_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/rate-limits/{client_id}"]["surface_id"] == "rate_limit_read_models"
    assert closure_actions["classify_rate_limit_read_model_routes"]["status"] == "closed"


def test_feature_flag_read_model_surface_exposes_bounded_flag_checks() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    flag_surface = surfaces["feature_flag_read_models"]
    witnesses = set(flag_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert flag_surface["coverage_state"] == "witnessed"
    assert flag_surface["request_proof"] == "read_model"
    assert flag_surface["action_proof"] == "read_model"
    assert "/api/v1/flags" in flag_surface["representative_paths"]
    assert "/api/v1/flags/{flag_id}" in flag_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/ops/feature_flags.py" in flag_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/feature_flags.py" in flag_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase220.py" in flag_surface["evidence_files"]
    assert "mcoi/tests/test_feature_flags.py" in flag_surface["evidence_files"]
    assert "feature_flags_list_returns_registered_flags" in witnesses
    assert "feature_flags_summary_counts_enabled_disabled" in witnesses
    assert "feature_flag_check_enabled" in witnesses
    assert "feature_flag_unknown_returns_disabled" in witnesses
    assert "feature_flag_tenant_override_respected" in witnesses
    assert route_records["/api/v1/flags"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/flags"]["surface_id"] == "feature_flag_read_models"
    assert route_records["/api/v1/flags/{flag_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/flags/{flag_id}"]["surface_id"] == "feature_flag_read_models"
    assert closure_actions["classify_feature_flag_routes"]["status"] == "closed"


def test_operational_health_surface_exposes_bounded_read_models() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    health_surface = surfaces["operational_health_read_models"]
    witnesses = set(health_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert health_surface["coverage_state"] == "witnessed"
    assert health_surface["request_proof"] == "read_model"
    assert health_surface["action_proof"] == "read_model"
    assert "/api/v1/health/deep" in health_surface["representative_paths"]
    assert "/api/v1/health/score" in health_surface["representative_paths"]
    assert "/api/v1/health/v2" in health_surface["representative_paths"]
    assert "/api/v1/health/v3" in health_surface["representative_paths"]
    assert "/api/v1/readiness" in health_surface["representative_paths"]
    assert "/api/v1/deploy/readiness" in health_surface["representative_paths"]
    assert "/api/v1/release/latest" in health_surface["representative_paths"]
    assert "/api/v1/snapshot" in health_surface["representative_paths"]
    assert "/api/v1/cache/stats" in health_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/health.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/summaries.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/release.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/ops/snapshots.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/deep_health.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/health_aggregator.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/health_check_agg.py" in health_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/health_v3.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_deep_health.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_health_aggregator.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_health_check_agg.py" in health_surface["evidence_files"]
    assert "mcoi/tests/test_phase232.py" in health_surface["evidence_files"]
    assert "deep_health_components_bounded" in witnesses
    assert "health_score_range_bounded" in witnesses
    assert "health_v2_degraded_state_supported" in witnesses
    assert "health_v2_exception_sanitized" in witnesses
    assert "health_v3_recovery_tracking" in witnesses
    assert "production_readiness_checks_bounded" in witnesses
    assert "deployment_readiness_read_model_bounded" in witnesses
    assert "release_info_read_model_bounded" in witnesses
    assert "system_snapshot_read_model_bounded" in witnesses
    assert route_records["/api/v1/health/deep"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/health/deep"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/health/v3"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/health/v3"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/readiness"]["surface_id"] == "operational_health_read_models"
    assert route_records["/api/v1/release/latest"]["surface_id"] == "operational_health_read_models"
    assert closure_actions["classify_operational_health_read_model_routes"]["status"] == "closed"


def test_agent_orchestration_lifecycle_surface_tracks_plans_and_handoffs() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    orchestration_surface = surfaces["agent_orchestration_lifecycle"]
    witnesses = set(orchestration_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert orchestration_surface["coverage_state"] == "witnessed"
    assert orchestration_surface["request_proof"] == "request_proof"
    assert orchestration_surface["action_proof"] == "action_proof"
    assert "/api/v1/orchestration" in orchestration_surface["representative_paths"]
    assert "/api/v1/orchestration/plans" in orchestration_surface["representative_paths"]
    assert "/api/v1/orchestration/plans/{plan_id}" in orchestration_surface["representative_paths"]
    assert "/api/v1/orchestration/handoff" in orchestration_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in orchestration_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_orchestration.py" in orchestration_surface["evidence_files"]
    assert "mcoi/tests/test_agent_orchestration.py" in orchestration_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase216.py" in orchestration_surface["evidence_files"]
    assert "orchestration_summary_bounded" in witnesses
    assert "orchestration_plan_created_for_registered_agent" in witnesses
    assert "orchestration_missing_plan_bounded" in witnesses
    assert "orchestration_handoff_capability_checked" in witnesses
    assert "orchestration_quorum_required" in witnesses
    assert "orchestration_executor_errors_sanitized" in witnesses
    assert route_records["/api/v1/orchestration"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/orchestration"]["surface_id"] == "agent_orchestration_lifecycle"
    assert route_records["/api/v1/orchestration/plans/{plan_id}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/orchestration/plans/{plan_id}"]["surface_id"] == "agent_orchestration_lifecycle"
    assert closure_actions["classify_agent_orchestration_lifecycle_routes"]["status"] == "closed"


def test_workflow_execution_lifecycle_surface_tracks_execution_history_and_tracing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    workflow_surface = surfaces["workflow_execution_lifecycle"]
    witnesses = set(workflow_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert workflow_surface["coverage_state"] == "witnessed"
    assert workflow_surface["request_proof"] == "request_proof"
    assert workflow_surface["action_proof"] == "action_proof"
    assert "/api/v1/workflow/execute" in workflow_surface["representative_paths"]
    assert "/api/v1/workflow/history" in workflow_surface["representative_paths"]
    assert "/api/v1/workflow/traced" in workflow_surface["representative_paths"]
    assert "/api/v1/execute" in workflow_surface["representative_paths"]
    assert "/api/v1/pipeline/execute" in workflow_surface["representative_paths"]
    assert "/api/v1/templates/execute" in workflow_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/traced_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/tests/test_agent_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/tests/test_traced_workflow.py" in workflow_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase205.py" in workflow_surface["evidence_files"]
    assert "workflow_execute_emits_action_proof" in witnesses
    assert "workflow_invalid_capability_bounded" in witnesses
    assert "workflow_history_bounded" in witnesses
    assert "workflow_errors_sanitized" in witnesses
    assert "traced_workflow_emits_replay_trace" in witnesses
    assert "traced_workflow_recorder_errors_sanitized" in witnesses
    assert "legacy_execute_emits_action_proof" in witnesses
    assert "pipeline_execution_emits_action_proof" in witnesses
    assert "template_execution_governed" in witnesses
    assert route_records["/api/v1/workflow/execute"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/workflow/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert route_records["/api/v1/workflow/traced"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/workflow/traced"]["surface_id"] == "workflow_execution_lifecycle"
    assert route_records["/api/v1/pipeline/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert route_records["/api/v1/templates/execute"]["surface_id"] == "workflow_execution_lifecycle"
    assert closure_actions["classify_workflow_execution_lifecycle_routes"]["status"] == "closed"


def test_agent_chain_execution_lifecycle_surface_tracks_execution_and_history() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    chain_surface = surfaces["agent_chain_execution_lifecycle"]
    witnesses = set(chain_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert chain_surface["coverage_state"] == "witnessed"
    assert chain_surface["request_proof"] == "request_proof"
    assert chain_surface["action_proof"] == "action_proof"
    assert "/api/v1/chain/execute" in chain_surface["representative_paths"]
    assert "/api/v1/chain/history" in chain_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/agent.py" in chain_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/agent_chain.py" in chain_surface["evidence_files"]
    assert "mcoi/tests/test_agent_chain.py" in chain_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase215.py" in chain_surface["evidence_files"]
    assert "chain_execute_single_step" in witnesses
    assert "chain_execute_two_steps" in witnesses
    assert "chain_prev_template_propagates_output" in witnesses
    assert "chain_halt_on_failure_bounded" in witnesses
    assert "chain_skip_on_failure_continues" in witnesses
    assert "chain_returned_failure_redacted" in witnesses
    assert "chain_history_bounded" in witnesses
    assert route_records["/api/v1/chain/execute"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/chain/execute"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert route_records["/api/v1/chain/history"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/chain/history"]["surface_id"] == "agent_chain_execution_lifecycle"
    assert closure_actions["classify_agent_chain_execution_routes"]["status"] == "closed"


def test_certification_daemon_lifecycle_surface_tracks_status_ticks_and_force_runs() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    daemon_surface = surfaces["certification_daemon_lifecycle"]
    witnesses = set(daemon_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert daemon_surface["coverage_state"] == "witnessed"
    assert daemon_surface["request_proof"] == "request_proof"
    assert daemon_surface["action_proof"] == "action_proof"
    assert "/api/v1/daemon/status" in daemon_surface["representative_paths"]
    assert "/api/v1/daemon/tick" in daemon_surface["representative_paths"]
    assert "/api/v1/daemon/force" in daemon_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/daemon.py" in daemon_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/certification_daemon.py" in daemon_surface["evidence_files"]
    assert "mcoi/tests/test_certification_daemon.py" in daemon_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase200.py" in daemon_surface["evidence_files"]
    assert "daemon_status_bounded" in witnesses
    assert "daemon_tick_interval_gated" in witnesses
    assert "daemon_force_runs_when_disabled" in witnesses
    assert "daemon_force_returns_chain_hash" in witnesses
    assert "daemon_history_bounded" in witnesses
    assert "daemon_exceptions_sanitized" in witnesses
    assert route_records["/api/v1/daemon/status"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/daemon/status"]["surface_id"] == "certification_daemon_lifecycle"
    assert route_records["/api/v1/daemon/force"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/daemon/force"]["surface_id"] == "certification_daemon_lifecycle"
    assert closure_actions["classify_certification_daemon_lifecycle_routes"]["status"] == "closed"


def test_live_path_certification_lifecycle_surface_tracks_runs_and_history() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    certification_surface = surfaces["live_path_certification_lifecycle"]
    witnesses = set(certification_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert certification_surface["coverage_state"] == "witnessed"
    assert certification_surface["request_proof"] == "request_proof"
    assert certification_surface["action_proof"] == "action_proof"
    assert "/api/v1/certify" in certification_surface["representative_paths"]
    assert "/api/v1/certify/history" in certification_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/certify.py" in certification_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/live_path_certification.py" in certification_surface["evidence_files"]
    assert "mcoi/tests/test_live_path_certification.py" in certification_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase199.py" in certification_surface["evidence_files"]
    assert "certification_run_emits_action_proof" in witnesses
    assert "certification_run_returns_chain_hash" in witnesses
    assert "certification_run_records_five_steps" in witnesses
    assert "certification_steps_named" in witnesses
    assert "certification_history_bounded" in witnesses
    assert "certification_chain_hash_deterministic" in witnesses
    assert "certification_failures_bounded" in witnesses
    assert route_records["/api/v1/certify"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/certify"]["surface_id"] == "live_path_certification_lifecycle"
    assert route_records["/api/v1/certify/history"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/certify/history"]["surface_id"] == "live_path_certification_lifecycle"
    assert closure_actions["classify_live_path_certification_routes"]["status"] == "closed"


def test_runtime_state_persistence_lifecycle_surface_tracks_save_load_and_list() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    state_surface = surfaces["runtime_state_persistence_lifecycle"]
    witnesses = set(state_surface["runtime_witnesses"])
    route_records = {
        record["route"]: record
        for record in matrix["route_coverage"]["routes"]
    }

    assert state_surface["coverage_state"] == "witnessed"
    assert state_surface["request_proof"] == "request_proof"
    assert state_surface["action_proof"] == "action_proof"
    assert "/api/v1/state" in state_surface["representative_paths"]
    assert "/api/v1/state/save" in state_surface["representative_paths"]
    assert "/api/v1/state/{state_type}" in state_surface["representative_paths"]
    assert "mcoi/mcoi_runtime/app/routers/data/state.py" in state_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/state_persistence.py" in state_surface["evidence_files"]
    assert "mcoi/tests/test_state_persistence.py" in state_surface["evidence_files"]
    assert "mcoi/tests/test_server_phase212.py" in state_surface["evidence_files"]
    assert "state_save_returns_hash_bound_snapshot" in witnesses
    assert "state_load_roundtrip" in witnesses
    assert "state_load_missing_bounded" in witnesses
    assert "state_list_summary_bounded" in witnesses
    assert "state_save_rejects_path_traversal" in witnesses
    assert "state_load_rejects_path_traversal" in witnesses
    assert "state_hash_mismatch_rejected" in witnesses
    assert route_records["/api/v1/state"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/state"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert route_records["/api/v1/state/save"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/state/save"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert route_records["/api/v1/state/{state_type}"]["coverage_state"] == "witnessed"
    assert route_records["/api/v1/state/{state_type}"]["surface_id"] == "runtime_state_persistence_lifecycle"
    assert closure_actions["classify_runtime_state_persistence_routes"]["status"] == "closed"


def test_connector_self_healing_surface_emits_bounded_recovery_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    healing_surface = surfaces["connector_self_healing"]
    witnesses = set(healing_surface["runtime_witnesses"])

    assert healing_surface["coverage_state"] == "witnessed"
    assert healing_surface["request_proof"] == "request_proof"
    assert healing_surface["action_proof"] == "action_proof"
    assert "ConnectorSelfHealingEngine.evaluate" in healing_surface["representative_paths"]
    assert "gateway/connector_self_healing.py" in healing_surface["evidence_files"]
    assert "schemas/connector_self_healing_receipt.schema.json" in healing_surface["evidence_files"]
    assert "tests/test_gateway/test_connector_self_healing.py" in healing_surface["evidence_files"]
    assert "provider_success_not_assumed" in witnesses
    assert "write_failures_require_operator_review" in witnesses
    assert "missing_receipt_revokes_capability" in witnesses
    assert "connector_self_healing_schema_valid" in witnesses
    assert closure_actions["publish_connector_self_healing_receipt_contract"]["status"] == "closed"


def test_collaboration_case_surface_keeps_closure_non_terminal() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    collaboration_surface = surfaces["collaboration_cases"]
    witnesses = set(collaboration_surface["runtime_witnesses"])

    assert collaboration_surface["coverage_state"] == "witnessed"
    assert collaboration_surface["request_proof"] == "request_proof"
    assert collaboration_surface["action_proof"] == "action_proof"
    assert "CollaborationCaseManager.open_case" in collaboration_surface["representative_paths"]
    assert "CollaborationCaseManager.close_case" in collaboration_surface["representative_paths"]
    assert "gateway/collaboration_cases.py" in collaboration_surface["evidence_files"]
    assert "schemas/collaboration_case.schema.json" in collaboration_surface["evidence_files"]
    assert "tests/test_gateway/test_collaboration_cases.py" in collaboration_surface["evidence_files"]
    assert "approval_separation_required" in witnesses
    assert "pending_controls_block_case_closure" in witnesses
    assert "decider_authority_required" in witnesses
    assert "case_closure_not_terminal_command_closure" in witnesses
    assert "collaboration_case_schema_valid" in witnesses
    assert closure_actions["publish_collaboration_case_contract"]["status"] == "closed"


def test_capability_maturity_surface_is_evidence_derived() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    maturity_surface = surfaces["capability_maturity"]
    witnesses = set(maturity_surface["runtime_witnesses"])

    assert maturity_surface["coverage_state"] == "witnessed"
    assert maturity_surface["request_proof"] == "request_proof"
    assert maturity_surface["action_proof"] == "action_proof"
    assert "gateway/capability_maturity.py" in maturity_surface["evidence_files"]
    assert "schemas/capability_maturity.schema.json" in maturity_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_maturity.py" in maturity_surface["evidence_files"]
    assert "maturity_derived_from_evidence" in witnesses
    assert "effect_bearing_c6_requires_live_write" in witnesses
    assert "autonomy_requires_c7" in witnesses
    assert closure_actions["publish_capability_maturity_contract"]["status"] == "closed"


def test_policy_prover_surface_reports_counterexamples() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    prover_surface = surfaces["policy_prover"]
    witnesses = set(prover_surface["runtime_witnesses"])

    assert prover_surface["coverage_state"] == "witnessed"
    assert prover_surface["request_proof"] == "request_proof"
    assert prover_surface["action_proof"] == "action_proof"
    assert "gateway/policy_prover.py" in prover_surface["evidence_files"]
    assert "schemas/policy_proof_report.schema.json" in prover_surface["evidence_files"]
    assert "tests/test_gateway/test_policy_prover.py" in prover_surface["evidence_files"]
    assert "payment_requires_approval_counterexample" in witnesses
    assert "shell_requires_sandbox_counterexample" in witnesses
    assert "unknown_property_fails_closed" in witnesses
    assert closure_actions["publish_policy_prover_counterexample_contract"]["status"] == "closed"


def test_memory_lattice_surface_gates_planning_and_execution() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lattice_surface = surfaces["memory_lattice"]
    witnesses = set(lattice_surface["runtime_witnesses"])

    assert lattice_surface["coverage_state"] == "witnessed"
    assert lattice_surface["request_proof"] == "request_proof"
    assert lattice_surface["action_proof"] == "action_proof"
    assert "gateway/memory_lattice.py" in lattice_surface["evidence_files"]
    assert "schemas/memory_lattice.schema.json" in lattice_surface["evidence_files"]
    assert "tests/test_gateway/test_memory_lattice.py" in lattice_surface["evidence_files"]
    assert "raw_event_memory_not_directly_admitted" in witnesses
    assert "semantic_memory_requires_learning_admission" in witnesses
    assert "contradiction_and_stale_memory_block_execution" in witnesses
    assert closure_actions["publish_memory_lattice_admission_contract"]["status"] == "closed"


def test_workflow_mining_surface_emits_blocked_drafts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    mining_surface = surfaces["workflow_mining"]
    witnesses = set(mining_surface["runtime_witnesses"])

    assert mining_surface["coverage_state"] == "witnessed"
    assert mining_surface["request_proof"] == "request_proof"
    assert mining_surface["action_proof"] == "action_proof"
    assert "gateway/workflow_mining.py" in mining_surface["evidence_files"]
    assert "schemas/workflow_mining_report.schema.json" in mining_surface["evidence_files"]
    assert "tests/test_gateway/test_workflow_mining.py" in mining_surface["evidence_files"]
    assert "workflow_draft_activation_blocked" in witnesses
    assert "operator_review_required" in witnesses
    assert "risky_pattern_requires_approval_rules" in witnesses
    assert closure_actions["publish_workflow_mining_draft_contract"]["status"] == "closed"


def test_trust_ledger_surface_signs_terminal_evidence_bundles() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    trust_surface = surfaces["trust_ledger"]
    witnesses = set(trust_surface["runtime_witnesses"])

    assert trust_surface["coverage_state"] == "witnessed"
    assert trust_surface["request_proof"] == "request_proof"
    assert trust_surface["action_proof"] == "action_proof"
    assert "/evidence/bundles/{command_id}" in trust_surface["representative_paths"]
    assert "docs/65_trust_ledger_offline_verification.md" in trust_surface["evidence_files"]
    assert "gateway/trust_ledger.py" in trust_surface["evidence_files"]
    assert "scripts/verify_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_anchor_receipt.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_anchor_verification_report.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_bundle.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_bundle_verification_report.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_evidence_artifacts.schema.json" in trust_surface["evidence_files"]
    assert "schemas/trust_ledger_export_package.schema.json" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_evidence_bundle_endpoint.py" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_trust_ledger_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "tests/test_gateway/test_trust_ledger.py" in trust_surface["evidence_files"]
    assert "tests/test_verify_anchor_receipt.py" in trust_surface["evidence_files"]
    assert "terminal_certificate_id_required" in witnesses
    assert "bundle_hash_tamper_detection" in witnesses
    assert "offline_bundle_verification_report_schema_valid" in witnesses
    assert "hmac_signature_verification" in witnesses
    assert "offline_anchor_verifier_validates_schema_artifacts_and_signature" in witnesses
    assert "offline_anchor_artifact_root_tamper_detection" in witnesses
    assert "offline_anchor_schema_invalid_receipt_rejected" in witnesses
    assert "offline_anchor_package_hash_mismatch_rejected" in witnesses
    assert "offline_anchor_package_schema_invalid_rejected" in witnesses
    assert "offline_anchor_verification_report_schema_valid" in witnesses
    assert "offline_anchor_report_emits_package_identity" in witnesses
    assert "typed_artifact_root_required" in witnesses
    assert "anchor_receipt_hmac_verification" in witnesses
    assert "anchor_receipt_schema_valid" in witnesses
    assert "export_package_binds_bundle_receipt_and_artifact_files" in witnesses
    assert "export_package_rejects_receipt_identity_drift" in witnesses
    assert closure_actions["publish_trust_ledger_bundle_contract"]["status"] == "closed"
    assert closure_actions["publish_trust_ledger_anchor_receipt_contract"]["status"] == "closed"


def test_domain_operating_pack_surface_requires_certification_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    pack_surface = surfaces["domain_operating_pack"]
    witnesses = set(pack_surface["runtime_witnesses"])

    assert pack_surface["coverage_state"] == "witnessed"
    assert pack_surface["request_proof"] == "request_proof"
    assert pack_surface["action_proof"] == "action_proof"
    assert "gateway/domain_operating_pack.py" in pack_surface["evidence_files"]
    assert "schemas/domain_operating_pack.schema.json" in pack_surface["evidence_files"]
    assert "tests/test_gateway/test_domain_operating_pack.py" in pack_surface["evidence_files"]
    assert "builtin_domain_pack_catalog_complete" in witnesses
    assert "high_risk_pack_requires_approval_roles" in witnesses
    assert "domain_operating_pack_schema_valid" in witnesses
    assert closure_actions["publish_domain_operating_pack_contract"]["status"] == "closed"


def test_multimodal_operating_layer_surface_emits_source_bound_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    multimodal_surface = surfaces["multimodal_operating_layer"]
    witnesses = set(multimodal_surface["runtime_witnesses"])

    assert multimodal_surface["coverage_state"] == "witnessed"
    assert multimodal_surface["request_proof"] == "request_proof"
    assert multimodal_surface["action_proof"] == "action_proof"
    assert "gateway/multimodal_operating_layer.py" in multimodal_surface["evidence_files"]
    assert "schemas/multimodal_operation_receipt.schema.json" in multimodal_surface["evidence_files"]
    assert "tests/test_gateway/test_multimodal_operating_layer.py" in multimodal_surface["evidence_files"]
    assert "external_send_blocked_by_default" in witnesses
    assert "unknown_modality_fails_closed" in witnesses
    assert closure_actions["publish_multimodal_operation_receipt_contract"]["status"] == "closed"


def test_physical_action_boundary_surface_blocks_dispatch_without_safety_controls() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    physical_surface = surfaces["physical_action_boundary"]
    witnesses = set(physical_surface["runtime_witnesses"])

    assert physical_surface["coverage_state"] == "witnessed"
    assert physical_surface["request_proof"] == "request_proof"
    assert physical_surface["action_proof"] == "action_proof"
    assert "/operator/physical-capability-promotion-receipts" in physical_surface["representative_paths"]
    assert "/operator/physical-capability-promotion-receipts/console" in physical_surface["representative_paths"]
    assert "capsules/physical.json" in physical_surface["evidence_files"]
    assert "capabilities/physical/capability_pack.json" in physical_surface["evidence_files"]
    assert "gateway/capability_capsule_installer.py" in physical_surface["evidence_files"]
    assert "gateway/server.py" in physical_surface["evidence_files"]
    assert "gateway/physical_action_boundary.py" in physical_surface["evidence_files"]
    assert "gateway/physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "gateway/physical_capability_promotion_store.py" in physical_surface["evidence_files"]
    assert "gateway/physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "scripts/emit_physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "scripts/preflight_physical_capability_promotion.py" in physical_surface["evidence_files"]
    assert "scripts/produce_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "schemas/physical_action_receipt.schema.json" in physical_surface["evidence_files"]
    assert "schemas/physical_capability_promotion_receipt.schema.json" in physical_surface["evidence_files"]
    assert "tests/test_emit_physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_capability_capsule_installer.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_action_boundary.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_capability_pack.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_capability_promotion_receipt.py" in physical_surface["evidence_files"]
    assert "tests/test_gateway/test_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "tests/test_preflight_physical_capability_promotion.py" in physical_surface["evidence_files"]
    assert "tests/test_produce_physical_worker_canary.py" in physical_surface["evidence_files"]
    assert "physical_capability_pack_fixture_not_default_loaded" in witnesses
    assert "physical_sandbox_replay_admitted_without_production_gate" in witnesses
    assert "live_physical_capability_rejected_by_production_gate" in witnesses
    assert "physical_pack_projects_sandbox_only_evidence" in witnesses
    assert "physical_promotion_preflight_blocks_fixture_live_claim" in witnesses
    assert "physical_promotion_preflight_requires_live_safety_evidence" in witnesses
    assert "physical_promotion_preflight_accepts_full_evidence" in witnesses
    assert "physical_promotion_preflight_allows_sandbox_only_pack" in witnesses
    assert "physical_capsule_admission_runs_promotion_preflight" in witnesses
    assert "physical_capsule_admission_keeps_registry_unmutated_on_preflight_failure" in witnesses
    assert "physical_promotion_receipt_binds_forge_handoff_registry_preflight" in witnesses
    assert "physical_promotion_receipt_schema_valid" in witnesses
    assert "physical_promotion_receipt_cli_emits_schema_valid_bundle" in witnesses
    assert "physical_promotion_receipt_cli_blocks_missing_live_refs" in witnesses
    assert "physical_promotion_receipt_operator_endpoint_emits_bundle" in witnesses
    assert "physical_promotion_receipt_operator_endpoint_blocks_missing_live_refs" in witnesses
    assert "physical_promotion_receipt_jsonl_store_persists" in witnesses
    assert "physical_promotion_receipt_store_fails_closed_on_invalid_record" in witnesses
    assert "physical_promotion_receipt_operator_console_renders_ledger" in witnesses
    assert "hardware_identity_required" in witnesses
    assert "emergency_stop_required" in witnesses
    assert "physical_dispatch_blocked_until_controls_complete" in witnesses
    assert "physical_worker_canary_uses_sandbox_handler" in witnesses
    assert "physical_worker_canary_artifact_hash_bound" in witnesses
    assert closure_actions["publish_physical_action_receipt_contract"]["status"] == "closed"


def test_code_intelligence_operator_surface_is_read_only() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    code_surface = surfaces["code_intelligence_operator_read_model"]
    witnesses = set(code_surface["runtime_witnesses"])

    assert code_surface["coverage_state"] == "witnessed"
    assert code_surface["request_proof"] == "read_model"
    assert code_surface["action_proof"] == "read_model"
    assert "/operator/code-intelligence/read-model" in code_surface["representative_paths"]
    assert "build_repo_map" in code_surface["representative_paths"]
    assert "build_code_context" in code_surface["representative_paths"]
    assert "gateway/code_intelligence_read_model.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/code_intelligence.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/contracts/code_context.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_intelligence.py" in code_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/code_context_builder.py" in code_surface["evidence_files"]
    assert "tests/test_gateway/test_code_intelligence_read_model.py" in code_surface["evidence_files"]
    assert "code_intelligence_repo_map_detects_routes_schemas_dependencies" in witnesses
    assert "code_context_bundle_bounds_symbols_tests_and_edges" in witnesses
    assert "code_context_missing_affected_file_fails_closed" in witnesses
    assert "code_intelligence_operator_read_model_hides_source_content" in witnesses
    assert "code_intelligence_operator_endpoint_fails_closed_for_missing_file" in witnesses


def test_temporal_kernel_surface_owns_runtime_time_truth() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    temporal_surface = surfaces["temporal_kernel"]
    witnesses = set(temporal_surface["runtime_witnesses"])

    assert temporal_surface["coverage_state"] == "witnessed"
    assert temporal_surface["request_proof"] == "request_proof"
    assert temporal_surface["action_proof"] == "action_proof"
    assert "/api/v1/temporal/schedules" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/schedules/{schedule_id}" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/schedules/{schedule_id}/cancel" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/worker/tick" in temporal_surface["representative_paths"]
    assert "/api/v1/temporal/summary" in temporal_surface["representative_paths"]
    assert "TemporalKernel.evaluate" in temporal_surface["representative_paths"]
    assert "TrustedClock.now_utc" in temporal_surface["representative_paths"]
    assert "TrustedClock.monotonic_ns" in temporal_surface["representative_paths"]
    assert "gateway/temporal_kernel.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/temporal_scheduler.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/temporal_scheduler.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/temporal_scheduler_worker.py" in temporal_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/persistence/temporal_scheduler_store.py" in temporal_surface["evidence_files"]
    assert "schemas/temporal_operation_receipt.schema.json" in temporal_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_kernel.py" in temporal_surface["evidence_files"]
    assert "mcoi/tests/test_temporal_scheduler_router.py" in temporal_surface["evidence_files"]
    assert "runtime_clock_injected" in witnesses
    assert "monotonic_duration_measured" in witnesses
    assert "future_schedule_defers" in witnesses
    assert "approval_expiry_denies" in witnesses
    assert "stale_evidence_escalates" in witnesses
    assert "budget_window_checked" in witnesses
    assert "causal_preconditions_required" in witnesses
    assert "temporal_scheduler_routes_governed" in witnesses
    assert "schedule_read_models_persisted" in witnesses
    assert "worker_tick_certifies_proofs" in witnesses
    assert "cancel_emits_terminal_receipt" in witnesses
    assert "temporal_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_operation_receipt_contract"]["status"] == "closed"
    assert closure_actions["classify_temporal_scheduler_routes"]["status"] == "closed"


def test_temporal_evidence_freshness_surface_rechecks_required_evidence() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    evidence_surface = surfaces["temporal_evidence_freshness"]
    witnesses = set(evidence_surface["runtime_witnesses"])

    assert evidence_surface["coverage_state"] == "witnessed"
    assert evidence_surface["request_proof"] == "request_proof"
    assert evidence_surface["action_proof"] == "action_proof"
    assert "TemporalEvidenceFreshness.evaluate" in evidence_surface["representative_paths"]
    assert "EvidenceFreshnessClaim" in evidence_surface["representative_paths"]
    assert "TemporalEvidenceFreshnessReceipt" in evidence_surface["representative_paths"]
    assert "gateway/temporal_evidence_freshness.py" in evidence_surface["evidence_files"]
    assert "schemas/temporal_evidence_freshness_receipt.schema.json" in evidence_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_evidence_freshness.py" in evidence_surface["evidence_files"]
    assert "evidence_age_computed_from_runtime_clock" in witnesses
    assert "freshness_window_required_for_dispatch" in witnesses
    assert "stale_required_evidence_triggers_refresh" in witnesses
    assert "missing_required_evidence_blocks_dispatch" in witnesses
    assert "revoked_or_unverified_high_risk_evidence_blocks" in witnesses
    assert "expiring_evidence_warns_before_dispatch" in witnesses
    assert "temporal_evidence_freshness_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_evidence_freshness_receipt_contract"]["status"] == "closed"


def test_temporal_resolution_surface_resolves_phrases_with_runtime_time() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    resolution_surface = surfaces["temporal_resolution"]
    witnesses = set(resolution_surface["runtime_witnesses"])

    assert resolution_surface["coverage_state"] == "witnessed"
    assert resolution_surface["request_proof"] == "request_proof"
    assert resolution_surface["action_proof"] == "action_proof"
    assert "evaluate_temporal_resolution" in resolution_surface["representative_paths"]
    assert "TemporalResolutionRequest" in resolution_surface["representative_paths"]
    assert "TemporalResolutionReceipt" in resolution_surface["representative_paths"]
    assert "gateway/temporal_resolution.py" in resolution_surface["evidence_files"]
    assert "schemas/temporal_resolution_receipt.schema.json" in resolution_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_resolution.py" in resolution_surface["evidence_files"]
    assert "runtime_clock_owns_phrase_resolution" in witnesses
    assert "original_text_preserved" in witnesses
    assert "tenant_timezone_controls_local_resolution" in witnesses
    assert "relative_duration_resolved_from_injected_now" in witnesses
    assert "ambiguous_low_risk_phrase_uses_safe_default" in witnesses
    assert "ambiguous_high_risk_phrase_requires_clarification" in witnesses
    assert "business_day_resolution_skips_weekends_and_holidays" in witnesses
    assert "unsupported_phrase_fails_closed" in witnesses
    assert "temporal_resolution_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_resolution_receipt_contract"]["status"] == "closed"


def test_temporal_sla_surface_classifies_sla_read_models_and_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    sla_surface = surfaces["temporal_sla"]
    witnesses = set(sla_surface["runtime_witnesses"])

    assert sla_surface["coverage_state"] == "witnessed"
    assert sla_surface["request_proof"] == "request_proof"
    assert sla_surface["action_proof"] == "action_proof"
    assert "/api/v1/sla" in sla_surface["representative_paths"]
    assert "/api/v1/sla/violations" in sla_surface["representative_paths"]
    assert "TemporalSla.evaluate" in sla_surface["representative_paths"]
    assert "SlaPolicy" in sla_surface["representative_paths"]
    assert "SlaCase" in sla_surface["representative_paths"]
    assert "TemporalSlaReceipt" in sla_surface["representative_paths"]
    assert "gateway/temporal_sla.py" in sla_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/app/routers/data/sla.py" in sla_surface["evidence_files"]
    assert "mcoi/mcoi_runtime/core/sla_monitor.py" in sla_surface["evidence_files"]
    assert "schemas/temporal_sla_receipt.schema.json" in sla_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_sla.py" in sla_surface["evidence_files"]
    assert "mcoi/tests/test_sla_monitor.py" in sla_surface["evidence_files"]
    assert "mcoi/tests/test_sla_router.py" in sla_surface["evidence_files"]
    assert "runtime_clock_owns_sla_deadlines" in witnesses
    assert "business_time_deadlines_skip_closed_windows" in witnesses
    assert "approaching_deadline_warns_before_breach" in witnesses
    assert "breached_deadline_emits_escalation_reason" in witnesses
    assert "outside_business_window_holds_normal_dispatch" in witnesses
    assert "sla_evidence_and_scope_checked" in witnesses
    assert "sla_summary_read_model_bounded" in witnesses
    assert "sla_violations_read_model_bounded" in witnesses
    assert "temporal_sla_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_sla_receipt_contract"]["status"] == "closed"


def test_temporal_reapproval_surface_rechecks_execution_time_approval_grants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    reapproval_surface = surfaces["temporal_reapproval"]
    witnesses = set(reapproval_surface["runtime_witnesses"])

    assert reapproval_surface["coverage_state"] == "witnessed"
    assert reapproval_surface["request_proof"] == "request_proof"
    assert reapproval_surface["action_proof"] == "action_proof"
    assert "TemporalReapproval.evaluate" in reapproval_surface["representative_paths"]
    assert "ReapprovalRequest" in reapproval_surface["representative_paths"]
    assert "TemporalReapprovalReceipt" in reapproval_surface["representative_paths"]
    assert "gateway/temporal_reapproval.py" in reapproval_surface["evidence_files"]
    assert "schemas/temporal_reapproval_receipt.schema.json" in reapproval_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_reapproval.py" in reapproval_surface["evidence_files"]
    assert "runtime_clock_owns_reapproval_time" in witnesses
    assert "high_risk_approval_roles_required" in witnesses
    assert "expired_approval_requires_reapproval" in witnesses
    assert "revoked_or_out_of_scope_approval_blocks_dispatch" in witnesses
    assert "missing_approval_role_requires_reapproval" in witnesses
    assert "low_risk_action_does_not_require_reapproval" in witnesses
    assert "temporal_reapproval_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_reapproval_receipt_contract"]["status"] == "closed"


def test_temporal_dispatch_window_surface_rechecks_runtime_admission_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    dispatch_window_surface = surfaces["temporal_dispatch_window"]
    witnesses = set(dispatch_window_surface["runtime_witnesses"])

    assert dispatch_window_surface["coverage_state"] == "witnessed"
    assert dispatch_window_surface["request_proof"] == "request_proof"
    assert dispatch_window_surface["action_proof"] == "action_proof"
    assert "TemporalDispatchWindow.evaluate" in dispatch_window_surface["representative_paths"]
    assert "DispatchWindowRequest" in dispatch_window_surface["representative_paths"]
    assert "TemporalDispatchWindowReceipt" in dispatch_window_surface["representative_paths"]
    assert "gateway/temporal_dispatch_window.py" in dispatch_window_surface["evidence_files"]
    assert "schemas/temporal_dispatch_window_receipt.schema.json" in dispatch_window_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_dispatch_window.py" in dispatch_window_surface["evidence_files"]
    assert "runtime_clock_owns_dispatch_window_time" in witnesses
    assert "tenant_timezone_resolved" in witnesses
    assert "allowed_window_required_for_high_risk_dispatch" in witnesses
    assert "outside_allowed_window_defers_dispatch" in witnesses
    assert "active_blackout_defers_dispatch" in witnesses
    assert "holiday_closure_defers_dispatch" in witnesses
    assert "source_reapproval_bound_for_high_risk_dispatch" in witnesses
    assert "temporal_dispatch_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_dispatch_window_receipt_contract"]["status"] == "closed"


def test_temporal_budget_window_surface_rechecks_tenant_budget_periods() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    budget_window_surface = surfaces["temporal_budget_window"]
    witnesses = set(budget_window_surface["runtime_witnesses"])

    assert budget_window_surface["coverage_state"] == "witnessed"
    assert budget_window_surface["request_proof"] == "request_proof"
    assert budget_window_surface["action_proof"] == "action_proof"
    assert "TemporalBudgetWindow.evaluate" in budget_window_surface["representative_paths"]
    assert "BudgetWindowRequest" in budget_window_surface["representative_paths"]
    assert "TemporalBudgetWindowReceipt" in budget_window_surface["representative_paths"]
    assert "gateway/temporal_budget_window.py" in budget_window_surface["evidence_files"]
    assert "schemas/temporal_budget_window_receipt.schema.json" in budget_window_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_budget_window.py" in budget_window_surface["evidence_files"]
    assert "runtime_clock_owns_budget_window_time" in witnesses
    assert "tenant_timezone_resolves_budget_period" in witnesses
    assert "daily_weekly_monthly_budget_resets_computed" in witnesses
    assert "spend_snapshot_period_matches_active_window" in witnesses
    assert "projected_spend_blocks_over_limit_dispatch" in witnesses
    assert "future_budget_window_defers_dispatch" in witnesses
    assert "source_reapproval_bound_for_high_risk_budget_window" in witnesses
    assert "temporal_budget_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_budget_window_receipt_contract"]["status"] == "closed"


def test_temporal_causal_order_surface_rechecks_required_event_order() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    causal_order_surface = surfaces["temporal_causal_order"]
    witnesses = set(causal_order_surface["runtime_witnesses"])

    assert causal_order_surface["coverage_state"] == "witnessed"
    assert causal_order_surface["request_proof"] == "request_proof"
    assert causal_order_surface["action_proof"] == "action_proof"
    assert "TemporalCausalOrder.evaluate" in causal_order_surface["representative_paths"]
    assert "TemporalCausalOrderRequest" in causal_order_surface["representative_paths"]
    assert "TemporalCausalOrderReceipt" in causal_order_surface["representative_paths"]
    assert "gateway/temporal_causal_order.py" in causal_order_surface["evidence_files"]
    assert "schemas/temporal_causal_order_receipt.schema.json" in causal_order_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_causal_order.py" in causal_order_surface["evidence_files"]
    assert "runtime_clock_owns_causal_order_time" in witnesses
    assert "required_events_must_be_present" in witnesses
    assert "tenant_and_command_scope_checked" in witnesses
    assert "predecessor_edges_checked" in witnesses
    assert "out_of_order_events_block_dispatch" in witnesses
    assert "future_events_block_dispatch" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_causal_order_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_causal_order_receipt_contract"]["status"] == "closed"


def test_temporal_monotonic_duration_surface_rechecks_elapsed_time() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    duration_surface = surfaces["temporal_monotonic_duration"]
    witnesses = set(duration_surface["runtime_witnesses"])

    assert duration_surface["coverage_state"] == "witnessed"
    assert duration_surface["request_proof"] == "request_proof"
    assert duration_surface["action_proof"] == "action_proof"
    assert "TemporalMonotonicDuration.evaluate" in duration_surface["representative_paths"]
    assert "TemporalMonotonicDurationRequest" in duration_surface["representative_paths"]
    assert "TemporalMonotonicDurationReceipt" in duration_surface["representative_paths"]
    assert "gateway/temporal_monotonic_duration.py" in duration_surface["evidence_files"]
    assert "schemas/temporal_monotonic_duration_receipt.schema.json" in duration_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_monotonic_duration.py" in duration_surface["evidence_files"]
    assert "runtime_monotonic_clock_owns_duration_truth" in witnesses
    assert "wall_clock_not_used_for_duration" in witnesses
    assert "duration_limit_exceeded_blocks_dispatch" in witnesses
    assert "cooldown_lower_bound_defers_dispatch" in witnesses
    assert "monotonic_clock_regression_blocks_dispatch" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_monotonic_duration_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_monotonic_duration_receipt_contract"]["status"] == "closed"


def test_temporal_accepted_risk_expiry_surface_blocks_stale_risk() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    accepted_risk_surface = surfaces["temporal_accepted_risk_expiry"]
    witnesses = set(accepted_risk_surface["runtime_witnesses"])

    assert accepted_risk_surface["coverage_state"] == "witnessed"
    assert accepted_risk_surface["request_proof"] == "request_proof"
    assert accepted_risk_surface["action_proof"] == "action_proof"
    assert "TemporalAcceptedRiskExpiry.evaluate" in accepted_risk_surface["representative_paths"]
    assert "TemporalAcceptedRiskRequest" in accepted_risk_surface["representative_paths"]
    assert "TemporalAcceptedRiskExpiryReceipt" in accepted_risk_surface["representative_paths"]
    assert "gateway/temporal_accepted_risk_expiry.py" in accepted_risk_surface["evidence_files"]
    assert "schemas/temporal_accepted_risk_expiry_receipt.schema.json" in accepted_risk_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_accepted_risk_expiry.py" in accepted_risk_surface["evidence_files"]
    assert "runtime_clock_owns_accepted_risk_expiry" in witnesses
    assert "expired_accepted_risk_blocks_dispatch" in witnesses
    assert "revoked_or_closed_accepted_risk_blocks_dispatch" in witnesses
    assert "tenant_command_and_action_scope_checked" in witnesses
    assert "review_obligation_required" in witnesses
    assert "accepted_risk_evidence_refs_required" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_accepted_risk_expiry_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_accepted_risk_expiry_receipt_contract"]["status"] == "closed"


def test_temporal_credential_expiry_surface_blocks_expired_credentials() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    credential_surface = surfaces["temporal_credential_expiry"]
    witnesses = set(credential_surface["runtime_witnesses"])

    assert credential_surface["coverage_state"] == "witnessed"
    assert credential_surface["request_proof"] == "request_proof"
    assert credential_surface["action_proof"] == "action_proof"
    assert "TemporalCredentialExpiry.evaluate" in credential_surface["representative_paths"]
    assert "TemporalCredentialRequest" in credential_surface["representative_paths"]
    assert "TemporalCredentialExpiryReceipt" in credential_surface["representative_paths"]
    assert "gateway/temporal_credential_expiry.py" in credential_surface["evidence_files"]
    assert "schemas/temporal_credential_expiry_receipt.schema.json" in credential_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_credential_expiry.py" in credential_surface["evidence_files"]
    assert "runtime_clock_owns_credential_expiry" in witnesses
    assert "expired_credentials_block_dispatch" in witnesses
    assert "revoked_credentials_block_dispatch" in witnesses
    assert "provider_and_credential_scope_checked" in witnesses
    assert "rotation_pending_warns_before_dispatch" in witnesses
    assert "rotation_overdue_blocks_dispatch" in witnesses
    assert "credential_evidence_refs_required" in witnesses
    assert "secret_value_absence_verified" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_credential_expiry_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_credential_expiry_receipt_contract"]["status"] == "closed"


def test_temporal_retention_window_surface_rechecks_data_lifecycle_timing() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    retention_surface = surfaces["temporal_retention_window"]
    witnesses = set(retention_surface["runtime_witnesses"])

    assert retention_surface["coverage_state"] == "witnessed"
    assert retention_surface["request_proof"] == "request_proof"
    assert retention_surface["action_proof"] == "action_proof"
    assert "TemporalRetentionWindow.evaluate" in retention_surface["representative_paths"]
    assert "TemporalRetentionRequest" in retention_surface["representative_paths"]
    assert "TemporalRetentionWindowReceipt" in retention_surface["representative_paths"]
    assert "gateway/temporal_retention_window.py" in retention_surface["evidence_files"]
    assert "schemas/temporal_retention_window_receipt.schema.json" in retention_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_retention_window.py" in retention_surface["evidence_files"]
    assert "runtime_clock_owns_retention_timing" in witnesses
    assert "delete_before_delete_after_defers_action" in witnesses
    assert "archive_and_anonymize_wait_for_retention_until" in witnesses
    assert "legal_hold_blocks_lifecycle_action" in witnesses
    assert "overdue_retention_action_warns" in witnesses
    assert "tenant_scope_checked" in witnesses
    assert "retention_policy_ref_required" in witnesses
    assert "subject_evidence_refs_required" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_retention_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_retention_window_receipt_contract"]["status"] == "closed"


def test_temporal_rate_limit_window_surface_rechecks_token_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    rate_limit_surface = surfaces["temporal_rate_limit_window"]
    witnesses = set(rate_limit_surface["runtime_witnesses"])

    assert rate_limit_surface["coverage_state"] == "witnessed"
    assert rate_limit_surface["request_proof"] == "request_proof"
    assert rate_limit_surface["action_proof"] == "action_proof"
    assert "TemporalRateLimitWindow.evaluate" in rate_limit_surface["representative_paths"]
    assert "RateLimitWindowRequest" in rate_limit_surface["representative_paths"]
    assert "TemporalRateLimitWindowReceipt" in rate_limit_surface["representative_paths"]
    assert "gateway/temporal_rate_limit_window.py" in rate_limit_surface["evidence_files"]
    assert "schemas/temporal_rate_limit_window_receipt.schema.json" in rate_limit_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_rate_limit_window.py" in rate_limit_surface["evidence_files"]
    assert "runtime_clock_owns_rate_limit_window" in witnesses
    assert "tenant_endpoint_identity_scope_checked" in witnesses
    assert "active_window_admits_sufficient_tokens" in witnesses
    assert "exhausted_window_emits_retry_after" in witnesses
    assert "future_window_defers_dispatch" in witnesses
    assert "burst_limit_blocks_overlarge_request" in witnesses
    assert "stale_rate_limit_snapshot_blocks_dispatch" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_rate_limit_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_rate_limit_window_receipt_contract"]["status"] == "closed"


def test_temporal_retry_window_surface_rechecks_retry_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    retry_surface = surfaces["temporal_retry_window"]
    witnesses = set(retry_surface["runtime_witnesses"])

    assert retry_surface["coverage_state"] == "witnessed"
    assert retry_surface["request_proof"] == "request_proof"
    assert retry_surface["action_proof"] == "action_proof"
    assert "TemporalRetryWindow.evaluate" in retry_surface["representative_paths"]
    assert "RetryWindowRequest" in retry_surface["representative_paths"]
    assert "TemporalRetryWindowReceipt" in retry_surface["representative_paths"]
    assert "gateway/temporal_retry_window.py" in retry_surface["evidence_files"]
    assert "schemas/temporal_retry_window_receipt.schema.json" in retry_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_retry_window.py" in retry_surface["evidence_files"]
    assert "runtime_clock_owns_retry_window" in witnesses
    assert "retry_after_floor_checked" in witnesses
    assert "cooldown_window_defers_early_retry" in witnesses
    assert "max_attempts_block_exhausted_retry" in witnesses
    assert "expired_retry_window_blocks_dispatch" in witnesses
    assert "tenant_command_scope_checked" in witnesses
    assert "terminal_failure_blocks_retry" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_retry_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_retry_window_receipt_contract"]["status"] == "closed"


def test_temporal_lease_window_surface_rechecks_lease_ownership() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    lease_surface = surfaces["temporal_lease_window"]
    witnesses = set(lease_surface["runtime_witnesses"])

    assert lease_surface["coverage_state"] == "witnessed"
    assert lease_surface["request_proof"] == "request_proof"
    assert lease_surface["action_proof"] == "action_proof"
    assert "TemporalLeaseWindow.evaluate" in lease_surface["representative_paths"]
    assert "LeaseWindowRequest" in lease_surface["representative_paths"]
    assert "TemporalLeaseWindowReceipt" in lease_surface["representative_paths"]
    assert "gateway/temporal_lease_window.py" in lease_surface["evidence_files"]
    assert "schemas/temporal_lease_window_receipt.schema.json" in lease_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_lease_window.py" in lease_surface["evidence_files"]
    assert "runtime_clock_owns_lease_window" in witnesses
    assert "tenant_command_resource_worker_scope_checked" in witnesses
    assert "active_lease_admits_dispatch" in witnesses
    assert "near_expiry_lease_requires_renewal_warning" in witnesses
    assert "expired_lease_blocks_dispatch" in witnesses
    assert "released_or_revoked_lease_blocks_dispatch" in witnesses
    assert "fencing_token_required" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_lease_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_lease_window_receipt_contract"]["status"] == "closed"


def test_temporal_idempotency_window_surface_blocks_duplicate_dispatch() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    idempotency_surface = surfaces["temporal_idempotency_window"]
    witnesses = set(idempotency_surface["runtime_witnesses"])

    assert idempotency_surface["coverage_state"] == "witnessed"
    assert idempotency_surface["request_proof"] == "request_proof"
    assert idempotency_surface["action_proof"] == "action_proof"
    assert "TemporalIdempotencyWindow.evaluate" in idempotency_surface["representative_paths"]
    assert "IdempotencyWindowRequest" in idempotency_surface["representative_paths"]
    assert "TemporalIdempotencyWindowReceipt" in idempotency_surface["representative_paths"]
    assert "gateway/temporal_idempotency_window.py" in idempotency_surface["evidence_files"]
    assert "schemas/temporal_idempotency_window_receipt.schema.json" in idempotency_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_idempotency_window.py" in idempotency_surface["evidence_files"]
    assert "runtime_clock_owns_idempotency_window" in witnesses
    assert "new_idempotency_key_admits_dispatch" in witnesses
    assert "matching_replay_admits_uncommitted_dispatch" in witnesses
    assert "committed_effect_blocks_duplicate_dispatch" in witnesses
    assert "expired_idempotency_window_blocks_dispatch" in witnesses
    assert "request_fingerprint_mismatch_blocks_replay" in witnesses
    assert "tenant_command_action_scope_checked" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_idempotency_window_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_idempotency_window_receipt_contract"]["status"] == "closed"


def test_temporal_missed_run_surface_emits_skip_and_recovery_receipts() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    missed_run_surface = surfaces["temporal_missed_run"]
    witnesses = set(missed_run_surface["runtime_witnesses"])

    assert missed_run_surface["coverage_state"] == "witnessed"
    assert missed_run_surface["request_proof"] == "request_proof"
    assert missed_run_surface["action_proof"] == "action_proof"
    assert "evaluate_temporal_missed_run" in missed_run_surface["representative_paths"]
    assert "MissedRunRequest" in missed_run_surface["representative_paths"]
    assert "TemporalMissedRunReceipt" in missed_run_surface["representative_paths"]
    assert "gateway/temporal_missed_run.py" in missed_run_surface["evidence_files"]
    assert "schemas/temporal_missed_run_receipt.schema.json" in missed_run_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_missed_run.py" in missed_run_surface["evidence_files"]
    assert "runtime_clock_owns_missed_run_time" in witnesses
    assert "late_within_grace_preserves_dispatch_eligibility" in witnesses
    assert "expired_command_emits_missed_run_receipt" in witnesses
    assert "duplicate_dispatched_run_requires_terminal_receipt" in witnesses
    assert "recovery_due_requires_review_actions" in witnesses
    assert "tenant_command_action_scope_checked" in witnesses
    assert "high_risk_source_receipts_bound" in witnesses
    assert "temporal_missed_run_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_missed_run_receipt_contract"]["status"] == "closed"


def test_temporal_memory_surface_blocks_stale_or_superseded_memory() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    memory_surface = surfaces["temporal_memory"]
    witnesses = set(memory_surface["runtime_witnesses"])

    assert memory_surface["coverage_state"] == "witnessed"
    assert memory_surface["request_proof"] == "request_proof"
    assert memory_surface["action_proof"] == "action_proof"
    assert "TemporalMemory.evaluate" in memory_surface["representative_paths"]
    assert "TemporalMemoryRecord" in memory_surface["representative_paths"]
    assert "TemporalMemoryReceipt" in memory_surface["representative_paths"]
    assert "gateway/temporal_memory.py" in memory_surface["evidence_files"]
    assert "schemas/temporal_memory_receipt.schema.json" in memory_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_memory.py" in memory_surface["evidence_files"]
    assert "memory_age_computed_from_runtime_clock" in witnesses
    assert "stale_memory_requires_refresh" in witnesses
    assert "validity_window_blocks_expired_memory" in witnesses
    assert "superseded_memory_not_usable" in witnesses
    assert "confidence_decay_blocks_weak_memory" in witnesses
    assert "temporal_memory_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_memory_receipt_contract"]["status"] == "closed"


def test_temporal_memory_refresh_surface_creates_bounded_refresh_work() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    refresh_surface = surfaces["temporal_memory_refresh"]
    witnesses = set(refresh_surface["runtime_witnesses"])

    assert refresh_surface["coverage_state"] == "witnessed"
    assert refresh_surface["request_proof"] == "request_proof"
    assert refresh_surface["action_proof"] == "action_proof"
    assert "TemporalMemoryRefresh.evaluate" in refresh_surface["representative_paths"]
    assert "MemoryRefreshRequest" in refresh_surface["representative_paths"]
    assert "TemporalMemoryRefreshReceipt" in refresh_surface["representative_paths"]
    assert "gateway/temporal_memory_refresh.py" in refresh_surface["evidence_files"]
    assert "schemas/temporal_memory_refresh_receipt.schema.json" in refresh_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_memory_refresh.py" in refresh_surface["evidence_files"]
    assert "usable_memory_does_not_create_refresh_task" in witnesses
    assert "stale_memory_creates_bounded_refresh_task" in witnesses
    assert "evidence_type_coverage_gates_review_readiness" in witnesses
    assert "invalid_refresh_policy_blocks_task_creation" in witnesses
    assert "superseded_memory_blocks_reactivation" in witnesses
    assert "temporal_memory_refresh_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_memory_refresh_receipt_contract"]["status"] == "closed"


def test_temporal_scheduler_surface_requires_leases_and_retry_windows() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    scheduler_surface = surfaces["temporal_scheduler"]
    witnesses = set(scheduler_surface["runtime_witnesses"])

    assert scheduler_surface["coverage_state"] == "witnessed"
    assert scheduler_surface["request_proof"] == "request_proof"
    assert scheduler_surface["action_proof"] == "action_proof"
    assert "TemporalScheduler.evaluate" in scheduler_surface["representative_paths"]
    assert "ScheduledCommand" in scheduler_surface["representative_paths"]
    assert "TemporalSchedulerReceipt" in scheduler_surface["representative_paths"]
    assert "gateway/temporal_scheduler.py" in scheduler_surface["evidence_files"]
    assert "schemas/temporal_scheduler_receipt.schema.json" in scheduler_surface["evidence_files"]
    assert "tests/test_gateway/test_temporal_scheduler.py" in scheduler_surface["evidence_files"]
    assert "scheduled_command_requires_execute_at" in witnesses
    assert "idempotency_required" in witnesses
    assert "lease_acquired_before_dispatch" in witnesses
    assert "missed_run_receipt_emitted" in witnesses
    assert "retry_window_checked" in witnesses
    assert "high_risk_reapproval_required" in witnesses
    assert "active_lease_blocks_duplicate_execution" in witnesses
    assert "temporal_scheduler_receipt_schema_valid" in witnesses
    assert closure_actions["publish_temporal_scheduler_receipt_contract"]["status"] == "closed"


def test_policy_proof_report_surface_is_counterexample_backed() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    policy_surface = surfaces["policy_proof_report"]
    witnesses = set(policy_surface["runtime_witnesses"])

    assert policy_surface["coverage_state"] == "witnessed"
    assert policy_surface["request_proof"] == "request_proof"
    assert policy_surface["action_proof"] == "action_proof"
    assert "PolicyProver.prove" in policy_surface["representative_paths"]
    assert "gateway/policy_prover.py" in policy_surface["evidence_files"]
    assert "schemas/policy_proof_report.schema.json" in policy_surface["evidence_files"]
    assert "tests/test_gateway/test_policy_prover.py" in policy_surface["evidence_files"]
    assert "bounded_policy_cases_required" in witnesses
    assert "empty_invariants_rejected" in witnesses
    assert "counterexamples_are_concrete" in witnesses
    assert "proved_report_has_no_counterexamples" in witnesses
    assert "policy_weakening_forbidden" in witnesses
    assert "policy_proof_schema_valid" in witnesses
    assert closure_actions["publish_policy_proof_report_contract"]["status"] == "closed"


def test_autonomous_capability_upgrade_surface_keeps_plans_activation_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    upgrade_surface = surfaces["autonomous_capability_upgrade"]
    witnesses = set(upgrade_surface["runtime_witnesses"])

    assert upgrade_surface["coverage_state"] == "witnessed"
    assert upgrade_surface["request_proof"] == "request_proof"
    assert upgrade_surface["action_proof"] == "action_proof"
    assert "gateway/autonomous_capability_upgrade.py" in upgrade_surface["evidence_files"]
    assert "schemas/capability_upgrade_plan.schema.json" in upgrade_surface["evidence_files"]
    assert "tests/test_gateway/test_autonomous_capability_upgrade.py" in upgrade_surface["evidence_files"]
    assert "health_signal_requires_evidence_refs" in witnesses
    assert "upgrade_candidates_are_promotion_blocked" in witnesses
    assert "capability_upgrade_plan_schema_valid" in witnesses
    assert closure_actions["publish_capability_upgrade_plan_contract"]["status"] == "closed"


def test_autonomous_test_generation_surface_keeps_plans_activation_blocked() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    generation_surface = surfaces["autonomous_test_generation"]
    witnesses = set(generation_surface["runtime_witnesses"])

    assert generation_surface["coverage_state"] == "witnessed"
    assert generation_surface["request_proof"] == "request_proof"
    assert generation_surface["action_proof"] == "action_proof"
    assert "gateway/autonomous_test_generation.py" in generation_surface["evidence_files"]
    assert "schemas/autonomous_test_generation_plan.schema.json" in generation_surface["evidence_files"]
    assert "tests/test_gateway/test_autonomous_test_generation.py" in generation_surface["evidence_files"]
    assert "failure_trace_requires_evidence_refs" in witnesses
    assert "plans_are_activation_blocked" in witnesses
    assert "autonomous_test_generation_plan_schema_valid" in witnesses
    assert closure_actions["publish_autonomous_test_generation_plan_contract"]["status"] == "closed"


def test_representative_http_paths_are_declared() -> None:
    matrix = _load_fixture()
    routes = discover_declared_routes()

    assert "/api/v1/stream" in routes
    assert "/api/v1/chat/stream" in routes
    assert validate_matrix_routes(matrix, routes) == []


def test_generated_assurance_copy_matches_when_present() -> None:
    matrix = _load_fixture()

    assert CANONICAL_OUTPUT.exists()
    assert matrix["surfaces"]
    if ASSURANCE_OUTPUT.exists():
        assurance = json.loads(ASSURANCE_OUTPUT.read_text(encoding="utf-8"))
        assert [surface["surface_id"] for surface in assurance["surfaces"]] == [
            surface["surface_id"] for surface in matrix["surfaces"]
        ]


def test_operator_document_mentions_every_surface() -> None:
    matrix = _load_fixture()
    doc = DOC_OUTPUT.read_text(encoding="utf-8")

    assert doc == operator_document(matrix)
    assert all(f"`{surface['surface_id']}`" in doc for surface in matrix["surfaces"])
    assert all(f"`{action['action_id']}`" in doc for action in matrix["closure_actions"])
    assert "schema contract validation" in doc
    assert "deployment orchestration receipt schema contract" in doc
