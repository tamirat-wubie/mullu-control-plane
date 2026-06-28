"""Tests for the causal WorkflowRun contract validator.

Purpose: prove schema, risk, approval, rollback, validation, and receipt rules.
Governance scope: WorkflowRun lifecycle closure and no-false-success behavior.
Dependencies: scripts.validate_workflow_run and the governed demo fixture.
Invariants:
  - Read-only runs can close fast with evidence and receipts.
  - High-risk runs require approval before execution or closure.
  - External effects require rollback readiness before execution.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout

from scripts import validate_workflow_run as validator


def _fixture() -> dict[str, object]:
    return validator.load_json_object(validator.FIXTURE_PATH, "workflow-run fixture")


def test_governed_work_assistant_demo_fixture_passes() -> None:
    record = _fixture()
    errors = validator.validate_workflow_run_record(record)

    assert errors == []
    assert record["workflow_id"] == "governed_work_assistant.demo.v0"
    assert record["risk_class"] == "R1"
    assert record["lifecycle_state"] == "CLOSED"
    assert record["approval_refs"] == []
    assert record["boundary"]["external_effects_allowed"] is False
    assert record["validation_result"]["status"] == "PASS"


def test_read_only_tasks_can_close_without_approval() -> None:
    record = _fixture()
    errors = validator.validate_workflow_run_record(record)

    assert errors == []
    assert record["risk_class"] in {"R0", "R1"}
    assert record["approval_refs"] == []
    assert record["rollback_plan"]["rollback_required"] is False
    assert record["monitoring_state"]["monitoring_status"] == "not_required"
    assert record["receipt_refs"] == ["receipt://workflow-run/demo-v0/closure"]


def test_high_risk_tasks_require_approval_before_execution() -> None:
    record = copy.deepcopy(_fixture())
    record["risk_class"] = "R3"
    record["lifecycle_state"] = "EXECUTING"
    record["boundary"]["external_effects_allowed"] = True
    record["action_plan"]["external_effects_allowed"] = True
    record["approval_refs"] = []
    record["rollback_plan"] = {
        "reversibility_label": "REVERSIBLE",
        "rollback_required": True,
        "rollback_ready": True,
        "rollback_refs": ["rollback://workflow-run/demo-v0/external"],
        "compensating_action": ""
    }
    record["monitoring_state"] = {
        "monitoring_required": True,
        "monitoring_status": "active",
        "monitor_refs": ["monitor://workflow-run/demo-v0/external"]
    }

    errors = validator.validate_workflow_run_record(record)

    assert "workflow_run: high-risk action cannot pass approval gate without approval_refs" in errors
    assert len(errors) == 1
    assert record["risk_class"] == "R3"
    assert record["lifecycle_state"] == "EXECUTING"


def test_false_success_cannot_close_workflow_run() -> None:
    record = copy.deepcopy(_fixture())
    record["validation_result"]["goal_satisfied"] = False
    record["validation_result"]["status"] = "PASS_WITH_LIMITS"

    errors = validator.validate_workflow_run_record(record)

    assert "workflow_run: CLOSED requires validation_result.goal_satisfied true" in errors
    assert "workflow_run: CLOSED requires validation_result.status PASS" in errors
    assert len(errors) == 2
    assert record["lifecycle_state"] == "CLOSED"
    assert record["receipt_refs"]


def test_external_effect_requires_rollback_readiness() -> None:
    record = copy.deepcopy(_fixture())
    record["risk_class"] = "R3"
    record["lifecycle_state"] = "APPROVED"
    record["approval_refs"] = ["approval://workflow-run/demo-v0/external"]
    record["boundary"]["external_effects_allowed"] = True
    record["action_plan"]["external_effects_allowed"] = True
    record["rollback_plan"] = {
        "reversibility_label": "UNKNOWN",
        "rollback_required": False,
        "rollback_ready": False,
        "rollback_refs": [],
        "compensating_action": ""
    }
    record["monitoring_state"] = {
        "monitoring_required": False,
        "monitoring_status": "not_required",
        "monitor_refs": []
    }

    errors = validator.validate_workflow_run_record(record)

    assert "workflow_run: external effect requires rollback_required true" in errors
    assert "workflow_run: external effect requires rollback_ready true" in errors
    assert "workflow_run: external effect cannot use UNKNOWN reversibility" in errors
    assert "workflow_run: external effect requires rollback_refs or compensating_action" in errors
    assert "workflow_run: external effect requires monitoring_required true" in errors


def test_receipts_are_required_before_terminal_closure() -> None:
    record = copy.deepcopy(_fixture())
    record["receipt_refs"] = []
    record["validation_result"]["receipt_emitted"] = False

    errors = validator.validate_workflow_run_record(record)

    assert "workflow_run: terminal closure requires receipt_refs" in errors
    assert "workflow_run: CLOSED requires validation_result.receipt_emitted true" in errors
    assert len(errors) == 2
    assert record["lifecycle_state"] == "CLOSED"
    assert record["validation_result"]["goal_satisfied"] is True


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "workflow_run_validation_receipt"
    assert report["valid"] is True
    assert report["error_count"] == 0
    assert report["check_count"] == 8
    assert report["payload_path"] == "examples/workflow_run_governed_work_assistant_demo_v0.foundation.json"
