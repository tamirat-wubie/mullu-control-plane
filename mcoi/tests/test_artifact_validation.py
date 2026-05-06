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
    assert "approval_gated_command" in pilot_names


def test_validate_example_artifacts_strictly() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    errors = validate_artifacts.validate_example_artifacts(strict=True)

    assert errors == []
    assert len(inventory.config_paths) >= 5
    assert len(inventory.request_paths) >= 3
    assert len(inventory.auxiliary_paths) >= 1
    assert len(inventory.maf_runtime_fixture_paths) >= 89
    assert len(inventory.mcoi_runtime_fixture_paths) >= 69


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
