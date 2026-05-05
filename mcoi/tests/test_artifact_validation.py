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
    assert "approval_gated_command" in pilot_names


def test_validate_example_artifacts_strictly() -> None:
    inventory = validate_artifacts.discover_example_inventory()
    errors = validate_artifacts.validate_example_artifacts(strict=True)

    assert errors == []
    assert len(inventory.config_paths) >= 5
    assert len(inventory.request_paths) >= 3
    assert len(inventory.auxiliary_paths) >= 1
    assert len(inventory.maf_runtime_fixture_paths) >= 45


def test_validate_maf_runtime_fixtures_strictly() -> None:
    errors = validate_artifacts.validate_maf_runtime_fixtures(strict=True)

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
