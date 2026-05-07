"""Purpose: verify shipped example artifacts remain governed and executable in shape.
Governance scope: product-facing JSON artifact validation only.
Dependencies: artifact validation script and local example inventory.
Invariants: shipped config and request artifacts fail closed on drift and remain deterministic to discover.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_artifacts


def test_example_inventory_covers_shipped_and_pilot_artifacts() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    config_names = {path.name for path in inventory.config_paths}
    request_names = {path.name for path in inventory.request_paths}
    auxiliary_names = {path.name for path in inventory.auxiliary_paths}
    maf_runtime_fixture_names = {path.name for path in inventory.maf_runtime_fixture_paths}
    mcoi_runtime_fixture_names = {path.name for path in inventory.mcoi_runtime_fixture_paths}
    pilot_names = {path.name for path in inventory.pilot_directories}

    assert "config-local-dev.json" in config_names
    assert "request-echo.json" in request_names
    assert "input_document.json" in auxiliary_names
    assert "event_correlation.json" in maf_runtime_fixture_names
    assert "event_envelope.json" in maf_runtime_fixture_names
    assert "event_record.json" in maf_runtime_fixture_names
    assert "event_reaction.json" in maf_runtime_fixture_names
    assert "event_subscription.json" in maf_runtime_fixture_names
    assert "event_window.json" in maf_runtime_fixture_names
    assert "benchmark_scenario.json" in maf_runtime_fixture_names
    assert "benchmark_suite.json" in maf_runtime_fixture_names
    assert "benchmark_metric.json" in maf_runtime_fixture_names
    assert "benchmark_result.json" in maf_runtime_fixture_names
    assert "benchmark_run.json" in maf_runtime_fixture_names
    assert "adversarial_case.json" in maf_runtime_fixture_names
    assert "regression_record.json" in maf_runtime_fixture_names
    assert "capability_scorecard.json" in maf_runtime_fixture_names
    assert "work_queue_entry.json" in maf_runtime_fixture_names
    assert "assignment_record.json" in maf_runtime_fixture_names
    assert "job_state.json" in maf_runtime_fixture_names
    assert "follow_up_record.json" in maf_runtime_fixture_names
    assert "deadline_record.json" in maf_runtime_fixture_names
    assert "job_execution_record.json" in maf_runtime_fixture_names
    assert "job_pause_record.json" in maf_runtime_fixture_names
    assert "job_resume_record.json" in maf_runtime_fixture_names
    assert "goal_descriptor.json" in maf_runtime_fixture_names
    assert "goal_dependency.json" in maf_runtime_fixture_names
    assert "sub_goal.json" in maf_runtime_fixture_names
    assert "goal_execution_state.json" in maf_runtime_fixture_names
    assert "goal_replan_record.json" in maf_runtime_fixture_names
    assert "journal_entry.json" in maf_runtime_fixture_names
    assert "subsystem_snapshot.json" in maf_runtime_fixture_names
    assert "composite_checkpoint.json" in maf_runtime_fixture_names
    assert "restore_verification.json" in maf_runtime_fixture_names
    assert "journal_validation_result.json" in maf_runtime_fixture_names
    assert "replay_step_result.json" in maf_runtime_fixture_names
    assert "replay_session_result.json" in maf_runtime_fixture_names
    assert "workflow_stage.json" in maf_runtime_fixture_names
    assert "workflow_binding.json" in maf_runtime_fixture_names
    assert "workflow_descriptor.json" in maf_runtime_fixture_names
    assert "workflow_transition.json" in maf_runtime_fixture_names
    assert "stage_execution_result.json" in maf_runtime_fixture_names
    assert "workflow_execution_record.json" in maf_runtime_fixture_names
    assert "workflow_verification_record.json" in maf_runtime_fixture_names
    assert "operational_node.json" in maf_runtime_fixture_names
    assert "operational_edge.json" in maf_runtime_fixture_names
    assert "evidence_link.json" in maf_runtime_fixture_names
    assert "decision_link.json" in maf_runtime_fixture_names
    assert "obligation_link.json" in maf_runtime_fixture_names
    assert "state_delta.json" in maf_runtime_fixture_names
    assert "causal_path.json" in maf_runtime_fixture_names
    assert "graph_snapshot.json" in maf_runtime_fixture_names
    assert "graph_query_result.json" in maf_runtime_fixture_names
    assert "obligation_closure.json" in maf_runtime_fixture_names
    assert "obligation_escalation.json" in maf_runtime_fixture_names
    assert "obligation_record.json" in maf_runtime_fixture_names
    assert "obligation_transfer.json" in maf_runtime_fixture_names
    assert "service_function_template.json" in maf_runtime_fixture_names
    assert "role_descriptor.json" in maf_runtime_fixture_names
    assert "function_policy_binding.json" in maf_runtime_fixture_names
    assert "function_sla_profile.json" in maf_runtime_fixture_names
    assert "function_queue_profile.json" in maf_runtime_fixture_names
    assert "resource_budget.json" in maf_runtime_fixture_names
    assert "decision_factor.json" in maf_runtime_fixture_names
    assert "utility_profile.json" in maf_runtime_fixture_names
    assert "option_utility.json" in maf_runtime_fixture_names
    assert "decision_comparison.json" in maf_runtime_fixture_names
    assert "tradeoff_record.json" in maf_runtime_fixture_names
    assert "decision_policy.json" in maf_runtime_fixture_names
    assert "utility_verdict.json" in maf_runtime_fixture_names
    assert "assignment_policy.json" in maf_runtime_fixture_names
    assert "worker_capacity.json" in maf_runtime_fixture_names
    assert "team_queue_state.json" in maf_runtime_fixture_names
    assert "worker_profile.json" in maf_runtime_fixture_names
    assert "assignment_decision.json" in maf_runtime_fixture_names
    assert "handoff_record.json" in maf_runtime_fixture_names
    assert "workload_snapshot.json" in maf_runtime_fixture_names
    assert "function_outcome_record.json" in maf_runtime_fixture_names
    assert "function_metrics_snapshot.json" in maf_runtime_fixture_names
    assert "simulation_option.json" in maf_runtime_fixture_names
    assert "simulation_request.json" in maf_runtime_fixture_names
    assert "simulation_outcome.json" in maf_runtime_fixture_names
    assert "simulation_verdict.json" in maf_runtime_fixture_names
    assert "supervisor_policy.json" in maf_runtime_fixture_names
    assert "supervisor_health.json" in maf_runtime_fixture_names
    assert "runtime_heartbeat.json" in maf_runtime_fixture_names
    assert "supervisor_checkpoint.json" in maf_runtime_fixture_names
    assert "livelock_record.json" in maf_runtime_fixture_names
    assert "incident_record.json" in mcoi_runtime_fixture_names
    assert "recovery_decision.json" in mcoi_runtime_fixture_names
    assert "recovery_attempt.json" in mcoi_runtime_fixture_names
    assert "recovery_record.json" in mcoi_runtime_fixture_names
    assert "recovery_plan.json" in mcoi_runtime_fixture_names
    assert "failover_record.json" in mcoi_runtime_fixture_names
    assert "recovery_objective.json" in mcoi_runtime_fixture_names
    assert "delegation_request.json" in mcoi_runtime_fixture_names
    assert "delegation_result.json" in mcoi_runtime_fixture_names
    assert "handoff_record.json" in mcoi_runtime_fixture_names
    assert "merge_decision.json" in mcoi_runtime_fixture_names
    assert "conflict_record.json" in mcoi_runtime_fixture_names
    assert "case_record.json" in mcoi_runtime_fixture_names
    assert "case_assignment.json" in mcoi_runtime_fixture_names
    assert "evidence_collection.json" in mcoi_runtime_fixture_names
    assert "evidence_item.json" in mcoi_runtime_fixture_names
    assert "finding_record.json" in mcoi_runtime_fixture_names
    assert "review_record.json" in mcoi_runtime_fixture_names
    assert "case_decision.json" in mcoi_runtime_fixture_names
    assert "case_closure_report.json" in mcoi_runtime_fixture_names
    assert "case_snapshot.json" in mcoi_runtime_fixture_names
    assert "case_violation.json" in mcoi_runtime_fixture_names
    assert "continuity_plan.json" in mcoi_runtime_fixture_names
    assert "disruption_event.json" in mcoi_runtime_fixture_names
    assert "recovery_execution.json" in mcoi_runtime_fixture_names
    assert "verification_record.json" in mcoi_runtime_fixture_names
    assert "continuity_snapshot.json" in mcoi_runtime_fixture_names
    assert "continuity_violation.json" in mcoi_runtime_fixture_names
    assert "continuity_closure_report.json" in mcoi_runtime_fixture_names
    assert "human_task_record.json" in mcoi_runtime_fixture_names
    assert "review_packet.json" in mcoi_runtime_fixture_names
    assert "approval_board.json" in mcoi_runtime_fixture_names
    assert "board_member.json" in mcoi_runtime_fixture_names
    assert "board_vote.json" in mcoi_runtime_fixture_names
    assert "collaborative_decision.json" in mcoi_runtime_fixture_names
    assert "handoff_packet.json" in mcoi_runtime_fixture_names
    assert "human_workflow_snapshot.json" in mcoi_runtime_fixture_names
    assert "human_workflow_violation.json" in mcoi_runtime_fixture_names
    assert "human_workflow_closure_report.json" in mcoi_runtime_fixture_names
    assert "attestation_record.json" in mcoi_runtime_fixture_names
    assert "certification_record.json" in mcoi_runtime_fixture_names
    assert "assurance_assessment.json" in mcoi_runtime_fixture_names
    assert "assurance_evidence_binding.json" in mcoi_runtime_fixture_names
    assert "recertification_window.json" in mcoi_runtime_fixture_names
    assert "assurance_finding.json" in mcoi_runtime_fixture_names
    assert "assurance_decision.json" in mcoi_runtime_fixture_names
    assert "assurance_snapshot.json" in mcoi_runtime_fixture_names
    assert "assurance_violation.json" in mcoi_runtime_fixture_names
    assert "assurance_closure_report.json" in mcoi_runtime_fixture_names
    assert "governance_contract_record.json" in mcoi_runtime_fixture_names
    assert "contract_clause.json" in mcoi_runtime_fixture_names
    assert "commitment_record.json" in mcoi_runtime_fixture_names
    assert "sla_window.json" in mcoi_runtime_fixture_names
    assert "breach_record.json" in mcoi_runtime_fixture_names
    assert "remedy_record.json" in mcoi_runtime_fixture_names
    assert "renewal_window.json" in mcoi_runtime_fixture_names
    assert "contract_assessment.json" in mcoi_runtime_fixture_names
    assert "contract_snapshot.json" in mcoi_runtime_fixture_names
    assert "contract_closure_report.json" in mcoi_runtime_fixture_names
    assert "asset_record.json" in mcoi_runtime_fixture_names
    assert "configuration_item.json" in mcoi_runtime_fixture_names
    assert "inventory_record.json" in mcoi_runtime_fixture_names
    assert "asset_assignment.json" in mcoi_runtime_fixture_names
    assert "asset_dependency.json" in mcoi_runtime_fixture_names
    assert "lifecycle_event.json" in mcoi_runtime_fixture_names
    assert "asset_assessment.json" in mcoi_runtime_fixture_names
    assert "asset_snapshot.json" in mcoi_runtime_fixture_names
    assert "asset_violation.json" in mcoi_runtime_fixture_names
    assert "asset_closure_report.json" in mcoi_runtime_fixture_names
    assert "billing_account.json" in mcoi_runtime_fixture_names
    assert "invoice_record.json" in mcoi_runtime_fixture_names
    assert "charge_record.json" in mcoi_runtime_fixture_names
    assert "credit_record.json" in mcoi_runtime_fixture_names
    assert "penalty_record.json" in mcoi_runtime_fixture_names
    assert "dispute_record.json" in mcoi_runtime_fixture_names
    assert "revenue_snapshot.json" in mcoi_runtime_fixture_names
    assert "billing_decision.json" in mcoi_runtime_fixture_names
    assert "billing_violation.json" in mcoi_runtime_fixture_names
    assert "billing_closure_report.json" in mcoi_runtime_fixture_names
    assert "payment_record.json" in mcoi_runtime_fixture_names
    assert "settlement_record.json" in mcoi_runtime_fixture_names
    assert "collection_case.json" in mcoi_runtime_fixture_names
    assert "dunning_notice.json" in mcoi_runtime_fixture_names
    assert "cash_application.json" in mcoi_runtime_fixture_names
    assert "refund_record.json" in mcoi_runtime_fixture_names
    assert "writeoff_record.json" in mcoi_runtime_fixture_names
    assert "aging_snapshot.json" in mcoi_runtime_fixture_names
    assert "settlement_decision.json" in mcoi_runtime_fixture_names
    assert "settlement_closure_report.json" in mcoi_runtime_fixture_names
    assert "customer_record.json" in mcoi_runtime_fixture_names
    assert "account_record.json" in mcoi_runtime_fixture_names
    assert "product_record.json" in mcoi_runtime_fixture_names
    assert "subscription_record.json" in mcoi_runtime_fixture_names
    assert "entitlement_record.json" in mcoi_runtime_fixture_names
    assert "account_health_snapshot.json" in mcoi_runtime_fixture_names
    assert "customer_decision.json" in mcoi_runtime_fixture_names
    assert "customer_violation.json" in mcoi_runtime_fixture_names
    assert "customer_snapshot.json" in mcoi_runtime_fixture_names
    assert "customer_closure_report.json" in mcoi_runtime_fixture_names
    assert "partner_record.json" in mcoi_runtime_fixture_names
    assert "partner_account_link.json" in mcoi_runtime_fixture_names
    assert "ecosystem_agreement.json" in mcoi_runtime_fixture_names
    assert "revenue_share_record.json" in mcoi_runtime_fixture_names
    assert "partner_commitment.json" in mcoi_runtime_fixture_names
    assert "partner_health_snapshot.json" in mcoi_runtime_fixture_names
    assert "partner_decision.json" in mcoi_runtime_fixture_names
    assert "partner_violation.json" in mcoi_runtime_fixture_names
    assert "partner_snapshot.json" in mcoi_runtime_fixture_names
    assert "partner_closure_report.json" in mcoi_runtime_fixture_names
    assert "offering_record.json" in mcoi_runtime_fixture_names
    assert "package_record.json" in mcoi_runtime_fixture_names
    assert "bundle_record.json" in mcoi_runtime_fixture_names
    assert "listing_record.json" in mcoi_runtime_fixture_names
    assert "eligibility_rule.json" in mcoi_runtime_fixture_names
    assert "pricing_binding.json" in mcoi_runtime_fixture_names
    assert "marketplace_assessment.json" in mcoi_runtime_fixture_names
    assert "marketplace_snapshot.json" in mcoi_runtime_fixture_names
    assert "marketplace_violation.json" in mcoi_runtime_fixture_names
    assert "marketplace_closure_report.json" in mcoi_runtime_fixture_names
    assert "vendor_record.json" in mcoi_runtime_fixture_names
    assert "procurement_request.json" in mcoi_runtime_fixture_names
    assert "purchase_order.json" in mcoi_runtime_fixture_names
    assert "vendor_assessment.json" in mcoi_runtime_fixture_names
    assert "vendor_commitment.json" in mcoi_runtime_fixture_names
    assert "procurement_decision.json" in mcoi_runtime_fixture_names
    assert "procurement_renewal_window.json" in mcoi_runtime_fixture_names
    assert "vendor_violation.json" in mcoi_runtime_fixture_names
    assert "procurement_snapshot.json" in mcoi_runtime_fixture_names
    assert "procurement_closure_report.json" in mcoi_runtime_fixture_names
    assert "budget_envelope.json" in mcoi_runtime_fixture_names
    assert "spend_record.json" in mcoi_runtime_fixture_names
    assert "cost_estimate.json" in mcoi_runtime_fixture_names
    assert "connector_cost_profile.json" in mcoi_runtime_fixture_names
    assert "campaign_budget_binding.json" in mcoi_runtime_fixture_names
    assert "approval_threshold.json" in mcoi_runtime_fixture_names
    assert "budget_reservation.json" in mcoi_runtime_fixture_names
    assert "spend_forecast.json" in mcoi_runtime_fixture_names
    assert "budget_conflict.json" in mcoi_runtime_fixture_names
    assert "budget_decision.json" in mcoi_runtime_fixture_names
    assert "financial_health_snapshot.json" in mcoi_runtime_fixture_names
    assert "budget_closure_report.json" in mcoi_runtime_fixture_names
    assert "ledger_account.json" in mcoi_runtime_fixture_names
    assert "ledger_transaction.json" in mcoi_runtime_fixture_names
    assert "settlement_proof.json" in mcoi_runtime_fixture_names
    assert "anchor_record.json" in mcoi_runtime_fixture_names
    assert "wallet_record.json" in mcoi_runtime_fixture_names
    assert "ledger_decision.json" in mcoi_runtime_fixture_names
    assert "ledger_snapshot.json" in mcoi_runtime_fixture_names
    assert "ledger_violation.json" in mcoi_runtime_fixture_names
    assert "ledger_assessment.json" in mcoi_runtime_fixture_names
    assert "ledger_closure_report.json" in mcoi_runtime_fixture_names
    assert "tenant_record.json" in mcoi_runtime_fixture_names
    assert "workspace_record.json" in mcoi_runtime_fixture_names
    assert "environment_record.json" in mcoi_runtime_fixture_names
    assert "boundary_policy.json" in mcoi_runtime_fixture_names
    assert "workspace_binding.json" in mcoi_runtime_fixture_names
    assert "environment_promotion.json" in mcoi_runtime_fixture_names
    assert "isolation_violation.json" in mcoi_runtime_fixture_names
    assert "tenant_health.json" in mcoi_runtime_fixture_names
    assert "tenant_decision.json" in mcoi_runtime_fixture_names
    assert "tenant_closure_report.json" in mcoi_runtime_fixture_names
    assert "record_descriptor.json" in mcoi_runtime_fixture_names
    assert "retention_schedule.json" in mcoi_runtime_fixture_names
    assert "legal_hold_record.json" in mcoi_runtime_fixture_names
    assert "disposition_review.json" in mcoi_runtime_fixture_names
    assert "record_link.json" in mcoi_runtime_fixture_names
    assert "record_snapshot.json" in mcoi_runtime_fixture_names
    assert "record_violation.json" in mcoi_runtime_fixture_names
    assert "preservation_decision.json" in mcoi_runtime_fixture_names
    assert "disposal_decision.json" in mcoi_runtime_fixture_names
    assert "records_closure_report.json" in mcoi_runtime_fixture_names
    assert "change_request.json" in mcoi_runtime_fixture_names
    assert "change_plan.json" in mcoi_runtime_fixture_names
    assert "change_step.json" in mcoi_runtime_fixture_names
    assert "change_execution.json" in mcoi_runtime_fixture_names
    assert "change_approval_binding.json" in mcoi_runtime_fixture_names
    assert "change_evidence.json" in mcoi_runtime_fixture_names
    assert "rollback_plan.json" in mcoi_runtime_fixture_names
    assert "change_outcome.json" in mcoi_runtime_fixture_names
    assert "change_impact_assessment.json" in mcoi_runtime_fixture_names
    assert "approval_gated_command" in pilot_names


def test_validate_example_artifacts_strictly() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    errors = validate_artifacts.validate_example_artifacts(strict=True)

    assert errors == []
    assert len(inventory.config_paths) >= 5
    assert len(inventory.request_paths) >= 3
    assert len(inventory.auxiliary_paths) >= 1
    assert len(inventory.maf_runtime_fixture_paths) >= 89
    assert len(inventory.mcoi_runtime_fixture_paths) >= 180


def test_validate_maf_runtime_fixtures_strictly() -> None:
    errors = validate_artifacts.validate_maf_runtime_fixtures(strict=True)

    assert errors == []
    assert len(errors) == 0


def test_validate_mcoi_runtime_fixtures_strictly() -> None:
    errors = validate_artifacts.validate_mcoi_runtime_fixtures(strict=True)

    assert errors == []
    assert len(errors) == 0


def test_validate_documented_artifact_references_strictly() -> None:
    errors = validate_artifacts.validate_documented_artifact_references(strict=True)

    assert errors == []
    assert len(errors) == 0


def test_validate_operational_documents_strictly() -> None:
    errors = validate_artifacts.validate_operational_documents(strict=True)

    assert errors == []
    assert len(errors) == 0


def test_document_reference_text_rejects_ungoverned_paths() -> None:
    errors = validate_artifacts.validate_document_artifact_reference_text(
        document_name="doc.md",
        content="Use `mcoi/examples/request-echo.json` and `examples/pilots/ghost/config.json`.",
        expected_paths=("mcoi/examples/request-echo.json",),
        governed_paths={"mcoi/examples/request-echo.json"},
        strict=True,
    )

    assert len(errors) == 2
    assert any("ungoverned artifact path examples/pilots/ghost/config.json" in error for error in errors)
    assert any("unexpected governed artifact references" in error for error in errors)


def test_operational_document_text_rejects_stale_release_inventory() -> None:
    content = """
RELEASE_NOTES_v0.1.md
KNOWN_LIMITATIONS_v0.1.md
SECURITY_MODEL_v0.1.md
OPERATOR_GUIDE_v0.1.md
PILOT_WORKFLOWS_v0.1.md
PILOT_CHECKLIST_v0.1.md
PILOT_OPERATIONS_GUIDE_v0.1.md
pytest -q
cargo test
scripts/validate_schemas.py --strict
scripts/validate_artifacts.py --strict
All 4 profiles load correctly
default-safe
strict-approval
readonly-only
352+ tests
"""
    errors = validate_artifacts.validate_operational_document_text(
        document_name="RELEASE_CHECKLIST_v0.1.md",
        content=content,
        strict=True,
    )

    assert len(errors) == 3
    assert any("missing required literals" in error and "scripts/validate_release_status.py --strict" in error for error in errors)
    assert any("contains stale literals" in error for error in errors)
    assert any("missing built-in profiles" in error and "pilot-prod" in error for error in errors)


def test_validate_config_artifact_rejects_unknown_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "config-invalid.json"
    config_path.write_text(
        json.dumps(
            {
                "allowed_planning_classes": ["constraint"],
                "enabled_executor_routes": ["shell_command"],
                "enabled_observer_routes": ["filesystem"],
                "unexpected_key": "drift",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_config_artifact(config_path)

    assert len(errors) == 1
    assert "unknown config keys" in errors[0]
    assert config_path.name in errors[0]


def test_validate_request_artifact_rejects_unknown_fields(tmp_path: Path) -> None:
    request_path = tmp_path / "request-invalid.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "req-1",
                "subject_id": "operator-1",
                "goal_id": "goal-1",
                "template": {
                    "template_id": "tpl-1",
                    "action_type": "shell_command",
                    "command_argv": [sys.executable, "-c", "print('ok')"],
                },
                "bindings": {},
                "unexpected_field": True,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_request_artifact(request_path)

    assert len(errors) == 1
    assert "unsupported request fields" in errors[0]
    assert "unexpected_field" in errors[0]


def test_validate_request_artifact_accepts_runtime_binding_template(tmp_path: Path) -> None:
    request_path = tmp_path / "request-runtime-binding.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "req-bind-1",
                "subject_id": "operator-1",
                "goal_id": "goal-bind-1",
                "template": {
                    "template_id": "tpl-bind-1",
                    "action_type": "shell_command",
                    "command_argv": ["{python_executable}", "-c", "print('bound')"],
                },
                "bindings": {},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_request_artifact(request_path)
    payload = json.loads(request_path.read_text(encoding="utf-8"))

    assert errors == []
    assert payload["template"]["command_argv"][0] == "{python_executable}"
    assert request_path.name.endswith(".json")


def test_validate_auxiliary_pilot_artifact_accepts_shipped_document_input() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    auxiliary_path = next(
        path for path in inventory.auxiliary_paths if path.name == "input_document.json"
    )

    errors = validate_artifacts.validate_example_artifacts(strict=True)

    assert errors == []
    assert auxiliary_path.exists()
    assert auxiliary_path.parent.name == "document_to_action"


def test_validate_auxiliary_pilot_document_rejects_missing_required_fields(tmp_path: Path) -> None:
    auxiliary_path = tmp_path / "input_document.json"
    auxiliary_path.write_text(
        json.dumps(
            {
                "task": "backup_database",
                "target": "production_db",
                "notify_email": "ops@example.com",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_auxiliary_artifact(
        auxiliary_path,
        artifact_key="examples/pilots/document_to_action/input_document.json",
    )

    assert len(errors) == 1
    assert "missing auxiliary fields" in errors[0]
    assert "retention_days" in errors[0]


def test_validate_auxiliary_pilot_document_rejects_non_positive_retention_days(tmp_path: Path) -> None:
    auxiliary_path = tmp_path / "input_document.json"
    auxiliary_path.write_text(
        json.dumps(
            {
                "task": "backup_database",
                "target": "production_db",
                "retention_days": 0,
                "notify_email": "ops@example.com",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_auxiliary_artifact(
        auxiliary_path,
        artifact_key="examples/pilots/document_to_action/input_document.json",
    )

    assert len(errors) == 1
    assert "retention_days" in errors[0]
    assert "positive integer" in errors[0]


def test_validate_maf_runtime_fixture_rejects_score_rank_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "simulation_comparison.json"
    fixture_path.write_text(
        json.dumps(
            {
                "comparison_id": "simcmp-drift",
                "request_id": "simreq-drift",
                "ranked_option_ids": ["opt-safe"],
                "scores": {"opt-fast": 0.9},
                "top_risk_level": "low",
                "review_burden": 0.25,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "scores keys must match ranked_option_ids exactly" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_worker_capacity_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "worker_capacity.json"
    fixture_path.write_text(
        json.dumps(
            {
                "worker_id": "worker-drift",
                "max_concurrent": 5,
                "current_load": 2,
                "available_slots": 4,
                "updated_at": "2025-01-01T00:20:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "available_slots must equal max_concurrent - current_load" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_duplicate_workload_snapshot_workers(tmp_path: Path) -> None:
    fixture_path = tmp_path / "workload_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snap-drift",
                "team_id": "team-release",
                "worker_capacities": [
                    {
                        "worker_id": "worker-7",
                        "max_concurrent": 5,
                        "current_load": 2,
                        "available_slots": 3,
                        "updated_at": "2025-01-01T00:20:00+00:00",
                    },
                    {
                        "worker_id": "worker-7",
                        "max_concurrent": 4,
                        "current_load": 1,
                        "available_slots": 3,
                        "updated_at": "2025-01-01T00:20:00+00:00",
                    },
                ],
                "captured_at": "2025-01-01T00:21:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "must not repeat worker_id 'worker-7'" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_simulation_outcome_option_mismatch(tmp_path: Path) -> None:
    fixture_path = tmp_path / "simulation_outcome.json"
    fixture_path.write_text(
        json.dumps(
            {
                "outcome_id": "simout-drift",
                "option_id": "opt-safe",
                "consequence": {
                    "estimate_id": "con-drift",
                    "option_id": "opt-fast",
                    "affected_node_ids": ["job-42"],
                    "new_edges_count": 1,
                    "new_obligations_count": 0,
                    "blocked_nodes_count": 0,
                    "unblocked_nodes_count": 1,
                },
                "risk": {
                    "estimate_id": "risk-drift",
                    "option_id": "opt-safe",
                    "risk_level": "low",
                    "incident_probability": 0.1,
                    "review_burden": 1,
                    "provider_exposure_count": 0,
                    "verification_difficulty": "moderate",
                    "rationale": "bounded",
                },
                "obligation_projection": {
                    "projection_id": "oblproj-drift",
                    "option_id": "opt-safe",
                    "new_obligations": [],
                    "fulfilled_obligations": [],
                    "deadline_pressure": 0,
                },
                "simulated_at": "2025-01-01T00:35:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "consequence.option_id must match outcome option_id" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_event_correlation_root_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "event_correlation.json"
    fixture_path.write_text(
        json.dumps(
            {
                "correlation_id": "corr-drift",
                "event_ids": ["evt-100", "evt-101"],
                "root_event_id": "evt-999",
                "description": "causal chain drift",
                "created_at": "2025-01-01T00:04:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "root_event_id must be present in event_ids" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_obligation_transfer_same_owner(tmp_path: Path) -> None:
    fixture_path = tmp_path / "obligation_transfer.json"
    fixture_path.write_text(
        json.dumps(
            {
                "transfer_id": "xfr-drift",
                "obligation_id": "obl-42",
                "from_owner": {
                    "owner_id": "team-ops",
                    "owner_type": "team",
                    "display_name": "Operations",
                },
                "to_owner": {
                    "owner_id": "team-ops",
                    "owner_type": "team",
                    "display_name": "Operations",
                },
                "reason": "reassign",
                "transferred_at": "2025-01-01T00:10:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "from_owner.owner_id must differ from to_owner.owner_id" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_obligation_closure_non_terminal_state(tmp_path: Path) -> None:
    fixture_path = tmp_path / "obligation_closure.json"
    fixture_path.write_text(
        json.dumps(
            {
                "closure_id": "cls-drift",
                "obligation_id": "obl-42",
                "final_state": "active",
                "reason": "premature closure",
                "closed_by": "operator-1",
                "closed_at": "2025-01-01T00:09:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "final_state must be one of completed, expired, or cancelled" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_resource_budget_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "resource_budget.json"
    fixture_path.write_text(
        json.dumps(
            {
                "resource_id": "budget-overflow",
                "resource_type": "compute",
                "total": 100.0,
                "consumed": 70.0,
                "reserved": 40.0,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "consumed + reserved must not exceed total" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_benchmark_metric_pass_mismatch(tmp_path: Path) -> None:
    fixture_path = tmp_path / "benchmark_metric.json"
    fixture_path.write_text(
        json.dumps(
            {
                "metric_id": "metric-drift",
                "kind": "correctness",
                "name": "verification_closure_rate",
                "value": 0.8,
                "threshold": 0.9,
                "passed": True,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "passed must be true iff value >= threshold" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_scorecard_metric_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "capability_scorecard.json"
    fixture_path.write_text(
        json.dumps(
            {
                "scorecard_id": "scorecard-drift",
                "category": "governance",
                "status": "degraded",
                "pass_rate": 0.8,
                "metric_count": 4,
                "metrics_passing": 5,
                "adversarial_pass_rate": 0.75,
                "regressions": [],
                "confidence_trend": "downward",
                "assessed_at": "2025-01-01T00:33:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "metrics_passing cannot exceed metric_count" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_workflow_binding_unknown_stage(tmp_path: Path) -> None:
    fixture_path = tmp_path / "workflow_descriptor.json"
    fixture_path.write_text(
        json.dumps(
            {
                "workflow_id": "wf-drift",
                "name": "Broken workflow",
                "description": "binding drift",
                "stages": [
                    {
                        "stage_id": "stage-build",
                        "stage_type": "skill_execution",
                        "skill_id": "build-release",
                        "description": "Build the release artifact",
                        "predecessors": [],
                        "timeout_seconds": 600,
                    }
                ],
                "bindings": [
                    {
                        "binding_id": "binding-drift",
                        "source_stage_id": "stage-build",
                        "source_output_key": "artifact_id",
                        "target_stage_id": "stage-missing",
                        "target_input_key": "artifact_id",
                    }
                ],
                "created_at": "2025-01-01T00:50:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "target_stage_id references unknown stage_id 'stage-missing'" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_job_execution_empty_error(tmp_path: Path) -> None:
    fixture_path = tmp_path / "job_execution_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "job_id": "job-drift",
                "execution_id": "job-exec-drift",
                "status": "failed",
                "started_at": "2025-01-01T01:20:00+00:00",
                "outcome_summary": "approval gate blocked rollout completion",
                "errors": [""],
                "completed_at": "2025-01-01T01:25:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "errors[0]" in errors[0]
    assert "must be a non-empty string" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_goal_execution_state_overlap(tmp_path: Path) -> None:
    fixture_path = tmp_path / "goal_execution_state.json"
    fixture_path.write_text(
        json.dumps(
            {
                "goal_id": "goal-drift",
                "status": "replanning",
                "updated_at": "2025-01-01T01:30:00+00:00",
                "current_plan_id": "plan-drift",
                "completed_sub_goals": ["sg-shared"],
                "failed_sub_goals": ["sg-shared"],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "appear in both completed and failed" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_recovery_attempt_success_error_drift(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "recovery_attempt.json"
    fixture_path.write_text(
        json.dumps(
            {
                "attempt_id": "attempt-drift",
                "incident_id": "inc-drift",
                "decision_id": "decision-drift",
                "action": "reobserve",
                "succeeded": True,
                "started_at": "2026-04-02T09:16:00+00:00",
                "finished_at": "2026-04-02T09:17:00+00:00",
                "error_message": "unexpected residual error",
                "result_run_id": "run-44",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "succeeded recovery attempts must keep error_message null" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_recovery_attempt_reverse_time(tmp_path: Path) -> None:
    fixture_path = tmp_path / "recovery_attempt.json"
    fixture_path.write_text(
        json.dumps(
            {
                "attempt_id": "attempt-drift",
                "incident_id": "inc-drift",
                "decision_id": "decision-drift",
                "action": "reobserve",
                "succeeded": False,
                "started_at": "2026-04-02T09:18:00+00:00",
                "finished_at": "2026-04-02T09:17:00+00:00",
                "error_message": "observer timed out",
                "result_run_id": None,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "finished_at must be greater than or equal to started_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_not_applicable_decision_action_drift(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "recovery_decision.json"
    fixture_path.write_text(
        json.dumps(
            {
                "decision_id": "decision-drift",
                "incident_id": "inc-drift",
                "action": "retry",
                "status": "not_applicable",
                "reason": "incident is already closed",
                "autonomy_mode": "observe_only",
                "profile_id": "safe-readonly",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "not_applicable recovery decisions must use action 'no_action'" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_continuity_plan_rpo_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "continuity_plan.json"
    fixture_path.write_text(
        json.dumps(
            {
                "plan_id": "plan-drift",
                "name": "Plan drift",
                "tenant_id": "tenant-1",
                "scope": "service",
                "status": "active",
                "scope_ref_id": "svc-drift",
                "rto_minutes": 15,
                "rpo_minutes": 20,
                "failover_target_ref": "svc-drift-dr",
                "owner_ref": "owner-1",
                "created_at": "2026-04-03T08:00:00+00:00",
                "metadata": {"tier": "critical"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "rpo_minutes must be less than or equal to rto_minutes" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_terminal_recovery_execution_without_completion(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "recovery_execution.json"
    fixture_path.write_text(
        json.dumps(
            {
                "execution_id": "exec-drift",
                "recovery_plan_id": "rp-drift",
                "disruption_id": "dis-drift",
                "status": "completed",
                "executed_by": "operator-1",
                "started_at": "2026-04-03T08:06:00+00:00",
                "completed_at": "",
                "metadata": {"attempt_id": "attempt-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "terminal recovery executions must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_continuity_snapshot_active_count_drift(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "continuity_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot-drift",
                "total_plans": 3,
                "total_active_plans": 4,
                "total_recovery_plans": 2,
                "total_disruptions": 1,
                "total_failovers": 1,
                "total_recoveries": 1,
                "total_verifications": 1,
                "total_violations": 0,
                "total_objectives": 3,
                "captured_at": "2026-04-03T08:20:00+00:00",
                "metadata": {"tenant_id": "tenant-1"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_active_plans must not exceed total_plans" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_terminal_failover_without_completion(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "failover_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "failover_id": "failover-drift",
                "plan_id": "plan-drift",
                "disruption_id": "dis-drift",
                "disposition": "completed",
                "source_ref": "svc-a",
                "target_ref": "svc-b",
                "initiated_at": "2026-04-03T08:03:00+00:00",
                "completed_at": "",
                "metadata": {"mode": "active-passive"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "terminal failovers must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_recovery_objective_met_drift(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "recovery_objective.json"
    fixture_path.write_text(
        json.dumps(
            {
                "objective_id": "objective-drift",
                "plan_id": "plan-drift",
                "name": "RTO objective drift",
                "target_minutes": 15,
                "actual_minutes": 21,
                "met": True,
                "evaluated_at": "2026-04-03T08:18:00+00:00",
                "metadata": {"objective_type": "rto"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "met recovery objectives must keep actual_minutes less than or equal to target_minutes" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_unmet_recovery_objective_success_drift(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "recovery_objective.json"
    fixture_path.write_text(
        json.dumps(
            {
                "objective_id": "objective-drift",
                "plan_id": "plan-drift",
                "name": "RPO objective drift",
                "target_minutes": 15,
                "actual_minutes": 12,
                "met": False,
                "evaluated_at": "2026-04-03T08:18:00+00:00",
                "metadata": {"objective_type": "rpo"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "unmet recovery objectives must keep actual_minutes greater than target_minutes" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_self_delegation(tmp_path: Path) -> None:
    fixture_path = tmp_path / "delegation_request.json"
    fixture_path.write_text(
        json.dumps(
            {
                "delegation_id": "delegation-drift",
                "delegator_id": "operator-a",
                "delegate_id": "operator-a",
                "goal_id": "goal-drift",
                "action_scope": "execute_recovery_plan",
                "deadline": "2026-04-03T08:30:00+00:00",
                "metadata": {"priority": "high"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "delegator_id and delegate_id must be different" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_handoff_without_context_ids(tmp_path: Path) -> None:
    fixture_path = tmp_path / "handoff_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "handoff_id": "handoff-drift",
                "from_party": "operator-a",
                "to_party": "operator-b",
                "goal_id": "goal-drift",
                "context_ids": [],
                "handed_off_at": "2026-04-03T08:04:00+00:00",
                "metadata": {"shift": "primary"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'context_ids' must be a non-empty array" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_merge_with_single_source(tmp_path: Path) -> None:
    fixture_path = tmp_path / "merge_decision.json"
    fixture_path.write_text(
        json.dumps(
            {
                "merge_id": "merge-drift",
                "goal_id": "goal-drift",
                "source_ids": ["assessment-primary"],
                "outcome": "merged",
                "reason": "not enough sources",
                "resolved_at": "2026-04-03T08:10:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'source_ids' must contain at least two items" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_resolved_conflict_without_resolution_id(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "conflict_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "conflict_id": "conflict-drift",
                "goal_id": "goal-drift",
                "conflicting_ids": ["assessment-primary", "assessment-rollback"],
                "strategy": "escalate",
                "resolved": True,
                "resolution_id": None,
                "metadata": {"severity": "medium"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "resolved conflicts must carry resolution_id" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_closed_case_without_closed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "case_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "case_id": "case-drift",
                "tenant_id": "tenant-1",
                "kind": "incident",
                "severity": "high",
                "status": "closed",
                "title": "Case drift",
                "description": "Closed case without closure time.",
                "opened_by": "operator-a",
                "opened_at": "2026-04-03T08:00:00+00:00",
                "closed_at": "",
                "metadata": {"incident_id": "incident-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "closed cases must carry closed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_non_closed_case_with_closed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "case_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "case_id": "case-drift",
                "tenant_id": "tenant-1",
                "kind": "incident",
                "severity": "high",
                "status": "escalated",
                "title": "Case drift",
                "description": "Escalated case should not already be closed.",
                "opened_by": "operator-a",
                "opened_at": "2026-04-03T08:00:00+00:00",
                "closed_at": "2026-04-03T08:25:00+00:00",
                "metadata": {"incident_id": "incident-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "non-closed cases must keep closed_at empty" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_case_closure_reverse_time(tmp_path: Path) -> None:
    fixture_path = tmp_path / "case_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "case_id": "case-drift",
                "tenant_id": "tenant-1",
                "kind": "incident",
                "severity": "high",
                "status": "closed",
                "title": "Case drift",
                "description": "Case closure time drifts before opening.",
                "opened_by": "operator-a",
                "opened_at": "2026-04-03T08:10:00+00:00",
                "closed_at": "2026-04-03T08:05:00+00:00",
                "metadata": {"incident_id": "incident-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "closed_at must be greater than or equal to opened_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_evidence_collection_duplicates(tmp_path: Path) -> None:
    fixture_path = tmp_path / "evidence_collection.json"
    fixture_path.write_text(
        json.dumps(
            {
                "collection_id": "collection-drift",
                "case_id": "case-drift",
                "title": "Duplicate evidence collection",
                "evidence_ids": ["evidence-a", "evidence-a"],
                "created_at": "2026-04-03T08:18:00+00:00",
                "metadata": {"curated_by": "reviewer-a"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'evidence_ids' must not contain duplicates" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_finding_without_evidence(tmp_path: Path) -> None:
    fixture_path = tmp_path / "finding_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "finding_id": "finding-drift",
                "case_id": "case-drift",
                "severity": "high",
                "title": "Unsupported finding",
                "description": "A finding without evidence should fail closed.",
                "evidence_ids": [],
                "remediation": "Attach evidence before recording the finding.",
                "found_at": "2026-04-03T08:20:00+00:00",
                "metadata": {"owner": "review-team"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'evidence_ids' must be a non-empty array" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_snapshot_open_cases_over_total(tmp_path: Path) -> None:
    fixture_path = tmp_path / "case_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot-drift",
                "scope_ref_id": "tenant-drift",
                "total_cases": 2,
                "open_cases": 3,
                "total_evidence": 4,
                "total_reviews": 3,
                "total_findings": 2,
                "total_decisions": 2,
                "total_violations": 0,
                "captured_at": "2026-04-03T08:30:00+00:00",
                "metadata": {"captured_by": "audit-runtime"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'open_cases' must not exceed total_cases" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_review_packet_completion_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "review_packet.json"
    fixture_path.write_text(
        json.dumps(
            {
                "packet_id": "packet-drift",
                "tenant_id": "tenant-1",
                "scope": "case",
                "scope_ref_id": "case-drift",
                "review_mode": "parallel",
                "title": "Review packet drift",
                "reviewer_count": 2,
                "reviews_completed": 3,
                "reviews_approved": 1,
                "created_at": "2026-04-03T08:12:00+00:00",
                "metadata": {"board_ref": "board-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "reviews_completed must not exceed reviewer_count" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_review_packet_approval_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "review_packet.json"
    fixture_path.write_text(
        json.dumps(
            {
                "packet_id": "packet-drift",
                "tenant_id": "tenant-1",
                "scope": "case",
                "scope_ref_id": "case-drift",
                "review_mode": "parallel",
                "title": "Review packet drift",
                "reviewer_count": 2,
                "reviews_completed": 1,
                "reviews_approved": 2,
                "created_at": "2026-04-03T08:12:00+00:00",
                "metadata": {"board_ref": "board-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "reviews_approved must not exceed reviews_completed" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_board_quorum_over_member_count(tmp_path: Path) -> None:
    fixture_path = tmp_path / "approval_board.json"
    fixture_path.write_text(
        json.dumps(
            {
                "board_id": "board-drift",
                "tenant_id": "tenant-1",
                "name": "Drift board",
                "approval_mode": "quorum",
                "quorum_required": 3,
                "scope": "case",
                "scope_ref_id": "case-drift",
                "member_count": 2,
                "created_at": "2026-04-03T08:13:00+00:00",
                "metadata": {"owner": "governance"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "quorum_required must not exceed member_count" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_collaborative_decision_vote_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "collaborative_decision.json"
    fixture_path.write_text(
        json.dumps(
            {
                "decision_id": "decision-drift",
                "board_id": "board-drift",
                "scope_ref_id": "case-drift",
                "status": "approved",
                "total_votes": 2,
                "approvals": 2,
                "rejections": 1,
                "decided_by": "chair-drift",
                "decided_at": "2026-04-03T08:23:00+00:00",
                "metadata": {"decision_type": "case_closure"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "approvals plus rejections must not exceed total_votes" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_handoff_packet_to_self(tmp_path: Path) -> None:
    fixture_path = tmp_path / "handoff_packet.json"
    fixture_path.write_text(
        json.dumps(
            {
                "handoff_id": "handoff-drift",
                "tenant_id": "tenant-1",
                "scope": "case",
                "scope_ref_id": "case-drift",
                "from_ref": "review-board",
                "to_ref": "review-board",
                "direction": "human_to_human",
                "reason": "Invalid self handoff.",
                "handed_at": "2026-04-03T08:14:00+00:00",
                "metadata": {"source_run": "run-drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "from_ref and to_ref must be different" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_attestation_expiry_before_attested_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "attestation_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "attestation_id": "attestation-drift",
                "tenant_id": "tenant-1",
                "scope": "control",
                "scope_ref_id": "control-drift",
                "level": "high",
                "status": "granted",
                "attested_by": "auditor-a",
                "attested_at": "2026-04-04T09:00:00+00:00",
                "expires_at": "2026-04-03T09:00:00+00:00",
                "metadata": {"framework": "internal"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "expires_at must be greater than or equal to attested_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_completed_recertification_without_completed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "recertification_window.json"
    fixture_path.write_text(
        json.dumps(
            {
                "window_id": "window-drift",
                "certification_id": "certification-drift",
                "status": "completed",
                "starts_at": "2027-03-15T09:00:00+00:00",
                "ends_at": "2027-04-04T09:00:00+00:00",
                "completed_at": "",
                "metadata": {"cycle": "annual"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "completed recertification windows must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_assurance_snapshot_granted_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "assurance_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot-drift",
                "scope_ref_id": "tenant-drift",
                "total_attestations": 2,
                "granted_attestations": 3,
                "total_certifications": 2,
                "active_certifications": 1,
                "total_assessments": 4,
                "total_evidence_bindings": 5,
                "total_violations": 0,
                "captured_at": "2026-04-04T09:30:00+00:00",
                "metadata": {"captured_by": "assurance-monitor"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "granted_attestations must not exceed total_attestations" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_assurance_snapshot_active_certification_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "assurance_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot-drift",
                "scope_ref_id": "tenant-drift",
                "total_attestations": 2,
                "granted_attestations": 1,
                "total_certifications": 1,
                "active_certifications": 2,
                "total_assessments": 4,
                "total_evidence_bindings": 5,
                "total_violations": 0,
                "captured_at": "2026-04-04T09:30:00+00:00",
                "metadata": {"captured_by": "assurance-monitor"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active_certifications must not exceed total_certifications" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_contract_expiry_before_effective_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "governance_contract_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "contract_id": "contract-drift",
                "tenant_id": "tenant-1",
                "counterparty": "ops-team",
                "status": "active",
                "title": "Drift contract",
                "description": "Expiry cannot precede effective date.",
                "effective_at": "2026-04-04T10:00:00+00:00",
                "expires_at": "2026-04-03T10:00:00+00:00",
                "metadata": {"program": "drift"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "expires_at must be greater than or equal to effective_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_completed_renewal_without_completed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "renewal_window.json"
    fixture_path.write_text(
        json.dumps(
            {
                "window_id": "renewal-drift",
                "contract_id": "contract-drift",
                "status": "completed",
                "opens_at": "2026-12-01T00:00:00+00:00",
                "closes_at": "2026-12-31T23:59:59+00:00",
                "completed_at": "",
                "metadata": {"owner": "contract-ops"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "completed renewal windows must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_contract_assessment_commitment_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "contract_assessment.json"
    fixture_path.write_text(
        json.dumps(
            {
                "assessment_id": "assessment-drift",
                "contract_id": "contract-drift",
                "tenant_id": "tenant-1",
                "total_commitments": 2,
                "healthy_commitments": 1,
                "at_risk_commitments": 1,
                "breached_commitments": 1,
                "overall_compliance": 0.8,
                "assessed_at": "2026-04-04T10:10:00+00:00",
                "metadata": {"owner": "auditor"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "healthy_commitments plus at_risk_commitments plus breached_commitments must not exceed total_commitments" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_contract_snapshot_active_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "contract_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot-drift",
                "total_contracts": 1,
                "active_contracts": 2,
                "total_commitments": 3,
                "total_sla_windows": 2,
                "total_breaches": 0,
                "total_remedies": 0,
                "total_renewals": 1,
                "total_violations": 0,
                "captured_at": "2026-04-04T10:15:00+00:00",
                "metadata": {"captured_by": "monitor"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active_contracts must not exceed total_contracts" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_inventory_quantity_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "inventory_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "inventory_id": "inventory-drift",
                "asset_id": "asset-drift",
                "tenant_id": "tenant-1",
                "disposition": "assigned",
                "total_quantity": 5,
                "assigned_quantity": 4,
                "available_quantity": 2,
                "updated_at": "2026-04-05T09:10:00+00:00",
                "metadata": {"warehouse": "dc-a"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "assigned_quantity plus available_quantity must not exceed total_quantity" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_self_asset_dependency(tmp_path: Path) -> None:
    fixture_path = tmp_path / "asset_dependency.json"
    fixture_path.write_text(
        json.dumps(
            {
                "dependency_id": "dependency-drift",
                "asset_id": "asset-drift",
                "depends_on_asset_id": "asset-drift",
                "description": "Self dependency should fail closed.",
                "created_at": "2026-04-05T09:13:00+00:00",
                "metadata": {"dependency_type": "self"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "asset_id and depends_on_asset_id must be different" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_asset_snapshot_count_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "asset_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "snapshot-drift",
                "total_assets": 4,
                "total_active": 3,
                "total_retired": 2,
                "total_config_items": 4,
                "total_inventory": 3,
                "total_assignments": 2,
                "total_dependencies": 1,
                "total_violations": 0,
                "total_asset_value": 1000.0,
                "captured_at": "2026-04-05T09:30:00+00:00",
                "metadata": {"captured_by": "asset-monitor"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_active plus total_retired must not exceed total_assets" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_asset_closure_count_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "asset_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "asset-closure-drift",
                "tenant_id": "tenant-1",
                "total_assets": 3,
                "total_active": 2,
                "total_retired": 2,
                "total_assignments": 1,
                "total_dependencies": 1,
                "total_asset_value": 1200.0,
                "closed_at": "2026-04-05T09:35:00+00:00",
                "metadata": {"closed_by": "asset-governance"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_active plus total_retired must not exceed total_assets" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_invoice_due_before_issue(tmp_path: Path) -> None:
    fixture_path = tmp_path / "invoice_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "invoice_id": "invoice-drift",
                "account_id": "billing-account-1",
                "tenant_id": "tenant-1",
                "status": "issued",
                "total_amount": 100.0,
                "currency": "USD",
                "issued_at": "2026-04-05T10:05:00+00:00",
                "due_at": "2026-04-04T10:05:00+00:00",
                "metadata": {"period": "2026-04"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "due_at must not precede issued_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_resolved_dispute_without_resolved_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "dispute_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "dispute_id": "dispute-drift",
                "invoice_id": "invoice-1",
                "account_id": "billing-account-1",
                "status": "resolved_accepted",
                "reason": "Resolution witness is missing a closure time.",
                "amount": 25.0,
                "opened_at": "2026-04-05T10:05:00+00:00",
                "resolved_at": "",
                "metadata": {"reviewed_by": "billing-review"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'resolved_at' must be a non-empty ISO 8601 string" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_revenue_snapshot_dispute_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "revenue_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "revenue-snapshot-drift",
                "total_accounts": 2,
                "total_invoices": 1,
                "total_charges": 4,
                "total_credits": 0,
                "total_penalties": 0,
                "total_disputes": 2,
                "total_recognized_revenue": 500.0,
                "total_pending_revenue": 30.0,
                "total_violations": 0,
                "captured_at": "2026-04-12T18:00:00+00:00",
                "metadata": {"currency": "USD"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_disputes must not exceed total_invoices" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_billing_closure_dispute_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "billing_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "billing-closure-drift",
                "account_id": "billing-account-1",
                "tenant_id": "tenant-1",
                "total_invoices": 1,
                "total_charges": 2,
                "total_credits": 1,
                "total_penalties": 0,
                "total_disputes": 2,
                "total_revenue": 420.0,
                "closed_at": "2026-04-30T23:59:00+00:00",
                "metadata": {"period": "2026-04"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_disputes must not exceed total_invoices" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_settlement_balance_mismatch(tmp_path: Path) -> None:
    fixture_path = tmp_path / "settlement_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "settlement_id": "settlement-drift",
                "invoice_id": "invoice-1",
                "account_id": "billing-account-1",
                "total_amount": 1000.0,
                "paid_amount": 300.0,
                "credit_applied": 100.0,
                "outstanding": 700.0,
                "status": "partial",
                "currency": "USD",
                "created_at": "2026-04-21T09:00:00+00:00",
                "metadata": {"period": "2026-04"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "paid_amount plus credit_applied plus outstanding must equal total_amount" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_closed_collection_case_without_closed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "collection_case.json"
    fixture_path.write_text(
        json.dumps(
            {
                "case_id": "collection-case-drift",
                "invoice_id": "invoice-1",
                "account_id": "billing-account-1",
                "status": "closed",
                "outstanding_amount": 120.0,
                "dunning_count": 2,
                "opened_at": "2026-04-21T09:00:00+00:00",
                "closed_at": "",
                "metadata": {"owner": "collections"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'closed_at' must be a non-empty ISO 8601 string" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_aging_snapshot_classification_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "aging_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "aging-snapshot-drift",
                "total_settlements": 4,
                "total_open": 2,
                "total_partial": 2,
                "total_settled": 1,
                "total_disputed": 0,
                "total_written_off": 0,
                "total_outstanding": 100.0,
                "total_collected": 300.0,
                "total_refunded": 10.0,
                "total_collection_cases": 2,
                "captured_at": "2026-04-30T23:00:00+00:00",
                "metadata": {"currency": "USD"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "classified settlement counts must not exceed total_settlements" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_settlement_closure_refund_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "settlement_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "settlement-closure-drift",
                "account_id": "billing-account-1",
                "total_settlements": 4,
                "total_payments": 1,
                "total_refunds": 2,
                "total_writeoffs": 0,
                "total_collection_cases": 1,
                "total_collected": 300.0,
                "total_outstanding": 120.0,
                "closed_at": "2026-04-30T23:59:00+00:00",
                "metadata": {"period": "2026-04"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_refunds must not exceed total_payments" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_subscription_end_before_start(tmp_path: Path) -> None:
    fixture_path = tmp_path / "subscription_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "subscription_id": "subscription-drift",
                "account_id": "billing-account-1",
                "product_id": "product-1",
                "tenant_id": "tenant-1",
                "status": "active",
                "quantity": 1,
                "start_at": "2026-04-10T00:00:00+00:00",
                "end_at": "2026-04-09T00:00:00+00:00",
                "created_at": "2026-04-01T00:00:00+00:00",
                "metadata": {"plan": "standard"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "end_at must not precede start_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_entitlement_expiry_before_grant(tmp_path: Path) -> None:
    fixture_path = tmp_path / "entitlement_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "entitlement_id": "entitlement-drift",
                "account_id": "billing-account-1",
                "tenant_id": "tenant-1",
                "service_ref": "service-1",
                "status": "active",
                "granted_at": "2026-04-10T00:00:00+00:00",
                "expires_at": "2026-04-09T00:00:00+00:00",
                "metadata": {"scope": "runtime"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "expires_at must not precede granted_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_customer_snapshot_health_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "customer_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "customer-snapshot-drift",
                "total_customers": 2,
                "total_accounts": 3,
                "total_products": 2,
                "total_subscriptions": 4,
                "total_entitlements": 5,
                "total_health_snapshots": 4,
                "total_decisions": 1,
                "total_violations": 0,
                "captured_at": "2026-04-30T23:00:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_health_snapshots must not exceed total_accounts" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_customer_closure_account_underflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "customer_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "customer-closure-drift",
                "tenant_id": "tenant-1",
                "total_customers": 4,
                "total_accounts": 3,
                "total_products": 2,
                "total_subscriptions": 4,
                "total_entitlements": 5,
                "total_violations": 0,
                "closed_at": "2026-04-30T23:59:00+00:00",
                "metadata": {"period": "2026-04"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_accounts must be at least total_customers" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_partner_self_link(tmp_path: Path) -> None:
    fixture_path = tmp_path / "partner_account_link.json"
    fixture_path.write_text(
        json.dumps(
            {
                "link_id": "partner-link-drift",
                "partner_id": "shared-identity-7",
                "account_id": "shared-identity-7",
                "tenant_id": "tenant-1",
                "role": "integrator",
                "created_at": "2026-05-02T12:30:00+00:00",
                "metadata": {"source": "test"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "partner_id must not equal account_id" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_partner_share_amount_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "revenue_share_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "share_id": "share-drift",
                "partner_id": "partner-1",
                "agreement_id": "agreement-1",
                "tenant_id": "tenant-1",
                "gross_amount": 1000.0,
                "share_amount": 350.0,
                "share_pct": 0.2,
                "status": "settled",
                "created_at": "2026-05-02T12:00:00+00:00",
                "metadata": {"period": "2026-05"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "share_amount must not exceed gross_amount multiplied by share_pct" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_partner_snapshot_health_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "partner_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "partner-snapshot-drift",
                "total_partners": 3,
                "total_links": 4,
                "total_agreements": 3,
                "total_revenue_shares": 4,
                "total_commitments": 5,
                "total_health_snapshots": 5,
                "total_decisions": 2,
                "total_violations": 1,
                "captured_at": "2026-05-02T13:00:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_health_snapshots must not exceed total_partners" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_marketplace_standard_price_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "pricing_binding.json"
    fixture_path.write_text(
        json.dumps(
            {
                "binding_id": "pricing-binding-drift",
                "offering_id": "offering-1",
                "tenant_id": "tenant-1",
                "base_price": 500.0,
                "effective_price": 450.0,
                "disposition": "standard",
                "contract_ref": "contract-1",
                "created_at": "2026-05-03T10:00:00+00:00",
                "metadata": {"currency": "USD"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "standard pricing must keep effective_price equal to base_price" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_marketplace_active_offering_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "marketplace_assessment.json"
    fixture_path.write_text(
        json.dumps(
            {
                "assessment_id": "marketplace-assessment-drift",
                "tenant_id": "tenant-1",
                "total_offerings": 4,
                "active_offerings": 5,
                "total_listings": 6,
                "active_listings": 4,
                "total_packages": 3,
                "coverage_score": 0.72,
                "assessed_at": "2026-05-03T12:00:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active_offerings must not exceed total_offerings" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_marketplace_active_listing_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "marketplace_assessment.json"
    fixture_path.write_text(
        json.dumps(
            {
                "assessment_id": "marketplace-assessment-listing-drift",
                "tenant_id": "tenant-1",
                "total_offerings": 5,
                "active_offerings": 4,
                "total_listings": 3,
                "active_listings": 4,
                "total_packages": 2,
                "coverage_score": 0.65,
                "assessed_at": "2026-05-03T12:30:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active_listings must not exceed total_listings" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_procurement_purchase_order_zero_amount(tmp_path: Path) -> None:
    fixture_path = tmp_path / "purchase_order.json"
    fixture_path.write_text(
        json.dumps(
            {
                "po_id": "po-drift",
                "request_id": "request-1",
                "vendor_id": "vendor-1",
                "tenant_id": "tenant-1",
                "status": "issued",
                "amount": 0.0,
                "currency": "USD",
                "issued_at": "2026-05-05T10:00:00+00:00",
                "metadata": {"source": "test"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "amount must be positive for a purchase order" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_procurement_renewal_reverse_window(tmp_path: Path) -> None:
    fixture_path = tmp_path / "procurement_renewal_window.json"
    fixture_path.write_text(
        json.dumps(
            {
                "renewal_id": "renewal-drift",
                "vendor_id": "vendor-1",
                "contract_ref": "contract-1",
                "disposition": "pending",
                "opens_at": "2026-06-01T00:00:00+00:00",
                "closes_at": "2026-05-01T00:00:00+00:00",
                "metadata": {"source": "test"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "closes_at must not precede opens_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_procurement_closure_tally_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "procurement_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "procurement-closure-drift",
                "tenant_id": "tenant-1",
                "total_vendors": 4,
                "total_requests": 6,
                "total_purchase_orders": 5,
                "total_fulfilled": 4,
                "total_cancelled": 2,
                "total_procurement_value": 12000.0,
                "closed_at": "2026-05-31T23:59:00+00:00",
                "metadata": {"period": "2026-05"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_fulfilled plus total_cancelled must not exceed total_purchase_orders" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_budget_envelope_limit_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "budget_envelope.json"
    fixture_path.write_text(
        json.dumps(
            {
                "budget_id": "budget-drift",
                "name": "Launch budget drift",
                "scope": "campaign",
                "scope_ref_id": "campaign-launch-1",
                "currency": "USD",
                "limit_amount": 1000.0,
                "reserved_amount": 250.0,
                "consumed_amount": 900.0,
                "warning_threshold": 0.8,
                "hard_stop_threshold": 1.0,
                "active": True,
                "tags": ["launch", "runtime"],
                "created_at": "2026-05-06T09:00:00+00:00",
                "updated_at": "2026-05-06T09:30:00+00:00",
                "metadata": {"cost_center": "growth"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "consumed_amount plus reserved_amount must not exceed limit_amount" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_approval_threshold_auto_approve_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "approval_threshold.json"
    fixture_path.write_text(
        json.dumps(
            {
                "threshold_id": "threshold-drift",
                "budget_id": "budget-1",
                "mode": "per_transaction",
                "amount": 500.0,
                "currency": "USD",
                "approver_ref": "finance-reviewer-1",
                "auto_approve_below": 750.0,
                "created_at": "2026-05-06T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "auto_approve_below must not exceed amount" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_spend_forecast_reverse_window(tmp_path: Path) -> None:
    fixture_path = tmp_path / "spend_forecast.json"
    fixture_path.write_text(
        json.dumps(
            {
                "forecast_id": "forecast-drift",
                "budget_id": "budget-1",
                "projected_amount": 1200.0,
                "currency": "USD",
                "period_start": "2026-06-30T00:00:00+00:00",
                "period_end": "2026-06-01T00:00:00+00:00",
                "confidence": 0.72,
                "breakdown": {
                    "connector_calls": 800.0,
                    "storage": 400.0
                },
                "created_at": "2026-05-06T11:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "period_start must be before period_end" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_budget_closure_overspend_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "budget_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "budget-closure-drift",
                "budget_id": "budget-1",
                "limit_amount": 1000.0,
                "total_consumed": 1200.0,
                "total_released": 150.0,
                "total_reservations": 4,
                "total_spend_records": 5,
                "currency": "USD",
                "under_budget": False,
                "overspend_amount": 150.0,
                "warnings_issued": 2,
                "hard_stops_triggered": 1,
                "closed_at": "2026-05-31T23:59:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "overspend_amount must equal max(total_consumed minus limit_amount, 0)" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_ledger_transaction_self_transfer(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ledger_transaction.json"
    fixture_path.write_text(
        json.dumps(
            {
                "transaction_id": "ledger-txn-drift",
                "tenant_id": "tenant-1",
                "from_account": "ledger-account-1",
                "to_account": "ledger-account-1",
                "amount": 125.0,
                "reference_ref": "invoice-1",
                "created_at": "2026-05-07T12:00:00+00:00",
                "metadata": {"network": "consortium"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "from_account must not equal to_account" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_confirmed_settlement_proof_without_verified_at(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "settlement_proof.json"
    fixture_path.write_text(
        json.dumps(
            {
                "proof_id": "proof-drift",
                "tenant_id": "tenant-1",
                "transaction_ref": "ledger-transaction-1",
                "status": "confirmed",
                "proof_hash": "sha256:proof-drift",
                "verified_at": "",
                "created_at": "2026-05-07T12:05:00+00:00",
                "metadata": {"anchor": "anchor-1"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "confirmed settlement proofs must carry verified_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_ledger_snapshot_proof_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ledger_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "ledger-snapshot-drift",
                "tenant_id": "tenant-1",
                "total_accounts": 3,
                "total_transactions": 4,
                "total_proofs": 5,
                "total_anchors": 3,
                "total_wallets": 2,
                "total_violations": 1,
                "captured_at": "2026-05-07T12:10:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_proofs must not exceed total_transactions" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_ledger_closure_proof_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ledger_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "ledger-closure-drift",
                "tenant_id": "tenant-1",
                "total_accounts": 3,
                "total_transactions": 8,
                "total_proofs": 9,
                "total_anchors": 4,
                "total_violations": 1,
                "created_at": "2026-05-31T23:59:00+00:00",
                "metadata": {"period": "2026-05"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_proofs must not exceed total_transactions" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_tenant_record_duplicate_workspaces(tmp_path: Path) -> None:
    fixture_path = tmp_path / "tenant_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tenant_id": "tenant-drift",
                "name": "Tenant Drift",
                "status": "active",
                "isolation_level": "strict",
                "owner": "tenant-admin-1",
                "workspace_ids": ["workspace-a", "workspace-a"],
                "created_at": "2026-05-07T11:00:00+00:00",
                "updated_at": "2026-05-07T11:10:00+00:00",
                "metadata": {"region": "us-east-1"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "workspace_ids must not contain duplicates" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_environment_promotion_terminal_without_completed_at(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "environment_promotion.json"
    fixture_path.write_text(
        json.dumps(
            {
                "promotion_id": "promotion-drift",
                "source_environment_id": "env-dev",
                "target_environment_id": "env-staging",
                "status": "completed",
                "compliance_check_passed": True,
                "promoted_by": "release-manager-1",
                "requested_at": "2026-05-07T11:15:00+00:00",
                "completed_at": "",
                "metadata": {"change_ref": "chg-1"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "terminal promotions must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_tenant_health_active_workspace_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "tenant_health.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tenant_id": "tenant-1",
                "total_workspaces": 3,
                "active_workspaces": 4,
                "total_environments": 5,
                "total_bindings": 7,
                "total_violations": 1,
                "compliance_pct": 0.93,
                "assessed_at": "2026-05-07T11:20:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active_workspaces must not exceed total_workspaces" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_tenant_closure_promotion_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "tenant_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "tenant-closure-drift",
                "tenant_id": "tenant-1",
                "total_workspaces": 2,
                "total_environments": 3,
                "total_bindings": 4,
                "total_promotions": 5,
                "total_violations": 1,
                "total_decisions": 2,
                "compliance_pct": 0.91,
                "closed_at": "2026-05-31T23:59:00+00:00",
                "metadata": {"period": "2026-05"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_promotions must not exceed total_environments" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_retention_schedule_reverse_expiry(tmp_path: Path) -> None:
    fixture_path = tmp_path / "retention_schedule.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schedule_id": "retention-drift",
                "record_id": "record-1",
                "tenant_id": "tenant-1",
                "retention_days": 90,
                "status": "active",
                "disposal_disposition": "archive",
                "scope_ref_id": "scope-1",
                "created_at": "2026-05-07T10:00:00+00:00",
                "expires_at": "2026-05-01T10:00:00+00:00",
                "metadata": {"policy": "default"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "expires_at must not precede created_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_active_legal_hold_with_released_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "legal_hold_record.json"
    fixture_path.write_text(
        json.dumps(
            {
                "hold_id": "hold-drift",
                "record_id": "record-1",
                "tenant_id": "tenant-1",
                "reason": "litigation hold",
                "authority": "legal",
                "status": "active",
                "placed_at": "2026-05-07T10:05:00+00:00",
                "released_at": "2026-05-08T10:05:00+00:00",
                "metadata": {"case_ref": "case-1"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active legal holds must keep released_at empty" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_record_snapshot_active_hold_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "record_snapshot.json"
    fixture_path.write_text(
        json.dumps(
            {
                "snapshot_id": "records-snapshot-drift",
                "scope_ref_id": "tenant-1",
                "total_records": 12,
                "total_schedules": 10,
                "total_holds": 3,
                "active_holds": 4,
                "total_links": 9,
                "total_disposals": 2,
                "total_violations": 1,
                "captured_at": "2026-05-07T10:10:00+00:00",
                "metadata": {"scope": "tenant"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "active_holds must not exceed total_holds" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_records_closure_tally_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "records_closure_report.json"
    fixture_path.write_text(
        json.dumps(
            {
                "report_id": "records-closure-drift",
                "tenant_id": "tenant-1",
                "total_records": 10,
                "total_preserved": 5,
                "total_disposed": 4,
                "total_held": 2,
                "total_violations": 1,
                "closed_at": "2026-05-31T23:59:00+00:00",
                "metadata": {"period": "2026-05"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "total_preserved plus total_disposed plus total_held must not exceed total_records" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_change_execution_step_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "change_execution.json"
    fixture_path.write_text(
        json.dumps(
            {
                "execution_id": "change-execution-drift",
                "change_id": "change-1",
                "plan_id": "plan-1",
                "status": "completed",
                "steps_total": 3,
                "steps_completed": 2,
                "steps_failed": 2,
                "rollout_mode": "phased",
                "started_at": "2026-05-07T12:15:00+00:00",
                "completed_at": "2026-05-07T13:05:00+00:00",
                "metadata": {"scope": "connector"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "steps_completed plus steps_failed must not exceed steps_total" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_terminal_change_step_without_completed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "change_step.json"
    fixture_path.write_text(
        json.dumps(
            {
                "step_id": "change-step-drift",
                "plan_id": "change-plan-1",
                "change_id": "change-1",
                "ordinal": 1,
                "action": "Promote routing rule to canary tier",
                "target_ref_id": "connector-openai-primary",
                "description": "Shift 25 percent of traffic to the candidate route.",
                "status": "completed",
                "started_at": "2026-05-07T12:30:00+00:00",
                "completed_at": "",
                "metadata": {"phase": "canary"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "terminal change steps must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_terminal_rollback_without_completed_at(tmp_path: Path) -> None:
    fixture_path = tmp_path / "rollback_plan.json"
    fixture_path.write_text(
        json.dumps(
            {
                "rollback_id": "rollback-drift",
                "change_id": "change-1",
                "disposition": "completed",
                "rollback_steps": ["restore-routing-baseline", "re-enable-fallback-priority"],
                "reason": "Latency degraded after the partial rollout.",
                "triggered_at": "2026-05-07T12:45:00+00:00",
                "completed_at": "",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "terminal rollback plans must carry completed_at" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_mcoi_runtime_fixture_rejects_change_outcome_without_observed_improvement(tmp_path: Path) -> None:
    fixture_path = tmp_path / "change_outcome.json"
    fixture_path.write_text(
        json.dumps(
            {
                "outcome_id": "change-outcome-drift",
                "change_id": "change-1",
                "execution_id": "execution-1",
                "status": "completed",
                "success": True,
                "improvement_observed": False,
                "improvement_pct": 0.15,
                "rollback_disposition": "not_needed",
                "evidence_count": 2,
                "completed_at": "2026-05-07T13:10:00+00:00",
                "metadata": {"baseline_latency_ms": 240.0},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_mcoi_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "improvement_pct must be 0 when improvement_observed is false" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_composite_checkpoint_duplicate_scope(tmp_path: Path) -> None:
    fixture_path = tmp_path / "composite_checkpoint.json"
    fixture_path.write_text(
        json.dumps(
            {
                "checkpoint_id": "checkpoint-drift",
                "epoch_id": "epoch-drift",
                "tick_number": 7,
                "snapshots": [
                    {
                        "snapshot_id": "snapshot-supervisor-a",
                        "scope": "supervisor",
                        "state_hash": "sha256:a",
                        "record_count": 3,
                        "captured_at": "2026-04-01T12:00:30+00:00",
                        "payload": {"policy_id": "policy-a"},
                    },
                    {
                        "snapshot_id": "snapshot-supervisor-b",
                        "scope": "supervisor",
                        "state_hash": "sha256:b",
                        "record_count": 4,
                        "captured_at": "2026-04-01T12:00:31+00:00",
                        "payload": {"policy_id": "policy-b"},
                    },
                ],
                "journal_sequence": 6,
                "composite_hash": "sha256:checkpoint-drift",
                "created_at": "2026-04-01T12:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "snapshots must not repeat scope values" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_restore_verification_hash_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "restore_verification.json"
    fixture_path.write_text(
        json.dumps(
            {
                "verification_id": "restore-drift",
                "checkpoint_id": "checkpoint-drift",
                "epoch_id": "epoch-drift",
                "tick_number": 7,
                "verdict": "verified",
                "expected_composite_hash": "sha256:expected",
                "actual_composite_hash": "sha256:actual",
                "subsystem_results": {
                    "supervisor": {
                        "state_hash": "sha256:supervisor",
                        "status": "verified",
                    }
                },
                "verified_at": "2026-04-01T12:02:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "verified restore_verification must keep expected_composite_hash equal to actual_composite_hash" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_journal_validation_gap_verdict_without_positions(
    tmp_path: Path,
) -> None:
    fixture_path = tmp_path / "journal_validation_result.json"
    fixture_path.write_text(
        json.dumps(
            {
                "validation_id": "journal-gap-drift",
                "epoch_id": "epoch-drift",
                "entry_count": 5,
                "first_sequence": 1,
                "last_sequence": 6,
                "verdict": "sequence_gap",
                "gap_positions": [],
                "detail": "missing journal entry",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "sequence_gap verdict requires at least one gap_positions entry" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_replay_session_tally_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "replay_session_result.json"
    fixture_path.write_text(
        json.dumps(
            {
                "session_id": "replay-session-drift",
                "epoch_id": "epoch-drift",
                "entries_replayed": 2,
                "entries_matched": 1,
                "entries_diverged": 0,
                "entries_skipped": 0,
                "verdict": "success",
                "steps": [
                    {
                        "step_id": "replay-step-1",
                        "sequence": 1,
                        "kind": "checkpoint",
                        "verdict": "match",
                        "expected_payload": {"checkpoint_id": "checkpoint-1"},
                        "actual_payload": {"checkpoint_id": "checkpoint-1"},
                        "detail": "payload matched",
                    }
                ],
                "started_at": "2026-04-01T12:03:00+00:00",
                "completed_at": "2026-04-01T12:04:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 2
    assert "entries_matched + entries_diverged + entries_skipped must equal entries_replayed" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_goal_plan_unknown_predecessor(tmp_path: Path) -> None:
    fixture_path = tmp_path / "goal_plan.json"
    fixture_path.write_text(
        json.dumps(
            {
                "plan_id": "plan-drift",
                "goal_id": "goal-drift",
                "sub_goals": [
                    {
                        "sub_goal_id": "sg-verify",
                        "goal_id": "goal-drift",
                        "description": "Run the governed verification workflow",
                        "status": "pending",
                        "skill_id": "verify-release",
                        "workflow_id": "wf-release-42",
                        "predecessors": ["sg-missing"],
                    }
                ],
                "created_at": "2025-01-01T00:05:00+00:00",
                "version": 2,
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "references unknown predecessor 'sg-missing'" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_decision_comparison_best_option_drift(tmp_path: Path) -> None:
    fixture_path = tmp_path / "decision_comparison.json"
    fixture_path.write_text(
        json.dumps(
            {
                "comparison_id": "cmp-drift",
                "profile_id": "profile-1",
                "option_utilities": [
                    {
                        "option_id": "opt-safe",
                        "raw_score": 0.8,
                        "weighted_score": 0.82,
                        "factor_contributions": {"factor-risk": 0.32},
                        "rank": 1,
                    }
                ],
                "best_option_id": "opt-missing",
                "spread": 0.1,
                "decided_at": "2025-01-01T00:20:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "best_option_id must reference an option in option_utilities" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_causal_path_without_edges(tmp_path: Path) -> None:
    fixture_path = tmp_path / "causal_path.json"
    fixture_path.write_text(
        json.dumps(
            {
                "path_id": "path-drift",
                "node_ids": ["goal-42", "job-42"],
                "edge_ids": [],
                "description": "broken causal path",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'edge_ids' must be a non-empty array" in errors[0]
    assert fixture_path.name in errors[0]


def test_validate_maf_runtime_fixture_rejects_evidence_link_confidence_overflow(tmp_path: Path) -> None:
    fixture_path = tmp_path / "evidence_link.json"
    fixture_path.write_text(
        json.dumps(
            {
                "edge_id": "evlink-drift",
                "source_node_id": "doc-42",
                "target_node_id": "verification-42",
                "evidence_type": "document_evidence",
                "confidence": 1.2,
                "created_at": "2025-01-01T00:25:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    errors = validate_artifacts.validate_maf_runtime_fixture(fixture_path)

    assert len(errors) == 1
    assert "field 'confidence' must be between 0.0 and 1.0" in errors[0]
    assert fixture_path.name in errors[0]
