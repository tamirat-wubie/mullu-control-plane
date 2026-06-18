"""Tests for the code-change physics packet.

Purpose: verify governance, creative, and repair physics planning artifacts stay
schema-valid, advisory-only, and bound to agentic-control code-change planning.
Governance scope: code-change physics doctrine, schema, example packet,
capability evidence binding, and selected-path no-bypass invariants.
Dependencies: scripts.validate_code_change_physics_packet.
Invariants:
  - Planning packets cannot grant execution authority.
  - Validated packets cannot select a live-effect path.
  - Governance, creative, and repair lanes all remain present.
"""

from __future__ import annotations

from copy import deepcopy
import io
import json
from contextlib import redirect_stdout

from scripts import validate_code_change_physics_packet as validator


def test_code_change_physics_artifacts_pass() -> None:
    findings = validator.validate_code_change_physics_packet()
    report = validator.build_validation_report()

    assert findings == []
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["check_count"] == 5


def test_packet_has_three_physics_lanes_and_creative_path() -> None:
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "code-change physics packet")
    findings = validator.validate_packet_semantics(packet)
    selected_candidate = {
        candidate["path_id"]: candidate
        for candidate in packet["candidate_paths"]
    }[packet["selected_path"]["path_id"]]

    assert findings == []
    assert set(packet["lanes"]) == validator.REQUIRED_LANES
    assert selected_candidate["requires_live_effect"] is False
    assert selected_candidate["path_kind"] == "approval_queue"


def test_packet_rejects_missing_repair_lane() -> None:
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "code-change physics packet")
    candidate = deepcopy(packet)
    candidate["lanes"].pop("repair_physics")

    findings = validator.validate_packet_semantics(candidate)

    assert findings
    assert any(finding.rule_id == "code_change_physics_lane_set_invalid" for finding in findings)
    assert not any(finding.rule_id == "code_change_physics_selected_path_unknown" for finding in findings)


def test_packet_rejects_validated_selected_live_effect() -> None:
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "code-change physics packet")
    candidate = deepcopy(packet)
    candidate["selected_path"]["path_id"] = "path:direct-live-effect"

    findings = validator.validate_packet_semantics(candidate)

    assert findings
    assert any(finding.rule_id == "code_change_physics_selected_live_effect_invalid" for finding in findings)
    assert candidate["status"] == "validated"


def test_packet_rejects_execution_authority_grant() -> None:
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "code-change physics packet")
    candidate = deepcopy(packet)
    candidate["selected_path"]["execution_authority_granted"] = True

    findings = validator.validate_packet_semantics(candidate)

    assert findings
    assert any(finding.rule_id == "code_change_physics_execution_authority_invalid" for finding in findings)
    assert candidate["selected_path"]["path_id"] == packet["selected_path"]["path_id"]


def test_agentic_control_code_change_plan_requires_physics_packet() -> None:
    pack = validator.load_json_object(validator.AGENTIC_CONTROL_PACK_PATH, "agentic-control capability pack")
    findings = validator.validate_agentic_control_binding(pack)
    code_change_entry = next(
        item for item in pack["capabilities"] if item["capability_id"] == "agentic_control.code_change.plan"
    )

    assert findings == []
    assert "code_change_physics_packet" in code_change_entry["evidence_model"]["required_evidence"]
    assert code_change_entry["extensions"]["governed_record"]["read_only"] is True


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "code_change_physics_packet_validation_receipt"
    assert report["valid"] is True
    assert report["error_count"] == 0
