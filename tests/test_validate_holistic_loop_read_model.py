"""Purpose: verify holistic loop read-model contract validation.
Governance scope: schema shape, current report validation, blocker/status
    consistency, and non-terminal closure fields.
Dependencies: scripts.validate_holistic_loop_read_model.
Invariants:
  - Current report output validates.
  - Count and blocker contradictions are rejected.
  - Closed or verified loops cannot carry missing evidence.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_holistic_loop_read_model as validator


def test_current_holistic_loop_read_model_contract_passes() -> None:
    errors = validator.validate_contract()
    report = validator.build_report()
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")

    assert errors == []
    assert schema["title"] == "Holistic Loop Read Model"
    assert report["report_id"] == "holistic_loop_read_model"
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True
    assert all(loop["authority_bindings"] for loop in report["loops"])
    assert all(loop["missing_authority"] for loop in report["loops"])
    assert all(loop["rollback_binding"] for loop in report["loops"])
    assert all(loop["step_receipts"] for loop in report["loops"])


def test_schema_rejects_missing_required_loop_field() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "open_blockers"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: open_blockers" in error for error in errors)
    assert "open_blockers" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_step_receipts() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "step_receipts"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: step_receipts" in error for error in errors)
    assert "step_receipts" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_authority_bindings() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "authority_bindings"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: authority_bindings" in error for error in errors)
    assert "authority_bindings" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_schema_requires_rollback_binding() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["$defs"]["loop_summary"]["required"] = [
        field for field in invalid_schema["$defs"]["loop_summary"]["required"] if field != "rollback_binding"
    ]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required loop field: rollback_binding" in error for error in errors)
    assert "rollback_binding" not in invalid_schema["$defs"]["loop_summary"]["required"]
    assert len(errors) >= 1


def test_blocked_count_mismatch_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["blocked_count"] = 0

    errors = validator.validate_report(invalid_report)

    assert "blocked_count does not match loop blockers" in errors
    assert invalid_report["blocked_count"] == 0
    assert report["blocked_count"] == 4


def test_status_mismatch_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("report status must be blocked" in error for error in errors)
    assert invalid_report["status"] == "verified"
    assert invalid_report["blocked_count"] == report["blocked_count"]


def test_missing_evidence_requires_matching_blocker() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["open_blockers"] = []

    errors = validator.validate_report(invalid_report)

    assert any("missing evidence lacks blocker" in error for error in errors)
    assert invalid_report["loops"][0]["missing_evidence"]
    assert invalid_report["loops"][0]["open_blockers"] == []


def test_missing_authority_requires_matching_blocker() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["open_blockers"] = [
        blocker
        for blocker in invalid_report["loops"][0]["open_blockers"]
        if not blocker.startswith("missing_authority:")
    ]

    errors = validator.validate_report(invalid_report)

    assert any("missing authority lacks blocker" in error for error in errors)
    assert invalid_report["loops"][0]["missing_authority"]
    assert all(
        not blocker.startswith("missing_authority:")
        for blocker in invalid_report["loops"][0]["open_blockers"]
    )


def test_missing_authority_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    missing_binding = invalid_report["loops"][0]["authority_bindings"].pop()

    errors = validator.validate_report(invalid_report)

    assert any("missing authority binding" in error for error in errors)
    assert missing_binding["authority_ref"] in invalid_report["loops"][0]["required_authority"]
    assert missing_binding not in invalid_report["loops"][0]["authority_bindings"]


def test_duplicate_authority_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["authority_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["authority_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate authority binding" in error for error in errors)
    assert invalid_report["loops"][0]["authority_bindings"][0]["authority_ref"]
    assert len(invalid_report["loops"][0]["authority_bindings"]) > len(
        invalid_report["loops"][0]["required_authority"]
    )


def test_authority_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["authority_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("authority binding 0 read_only must be true" in error for error in errors)
    assert any("authority binding 0 terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_rollback_binding_must_match_policy() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["rollback_binding"]["rollback_ref"] = "different_policy"

    errors = validator.validate_report(invalid_report)

    assert any("rollback_binding rollback_ref must match rollback_policy" in error for error in errors)
    assert invalid_report["loops"][0]["rollback_policy"] != invalid_report["loops"][0]["rollback_binding"][
        "rollback_ref"
    ]
    assert invalid_report["loops"][0]["rollback_binding"]["rollback_ref"] == "different_policy"


def test_rollback_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["rollback_binding"]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("rollback_binding read_only must be true" in error for error in errors)
    assert any("rollback_binding terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_missing_evidence_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    missing_binding = invalid_report["loops"][0]["evidence_bindings"].pop()

    errors = validator.validate_report(invalid_report)

    assert any("missing evidence binding" in error for error in errors)
    assert missing_binding["evidence_ref"] in invalid_report["loops"][0]["required_evidence"]
    assert missing_binding not in invalid_report["loops"][0]["evidence_bindings"]


def test_duplicate_evidence_binding_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["evidence_bindings"].append(
        copy.deepcopy(invalid_report["loops"][0]["evidence_bindings"][0])
    )

    errors = validator.validate_report(invalid_report)

    assert any("duplicate evidence binding" in error for error in errors)
    assert invalid_report["loops"][0]["evidence_bindings"][0]["evidence_ref"]
    assert len(invalid_report["loops"][0]["evidence_bindings"]) > len(
        invalid_report["loops"][0]["required_evidence"]
    )


def test_evidence_binding_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_binding = invalid_report["loops"][0]["evidence_bindings"][0]
    invalid_binding["read_only"] = False
    invalid_binding["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("read_only must be true" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert invalid_binding["read_only"] is False


def test_step_receipts_cannot_claim_mutation_or_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_receipt = invalid_report["loops"][0]["step_receipts"][0]
    invalid_receipt["metadata"]["read_only"] = False
    invalid_receipt["metadata"]["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("step receipt 0 read_only must be true" in error for error in errors)
    assert any("step receipt 0 terminal_closure must be false" in error for error in errors)
    assert invalid_receipt["metadata"]["read_only"] is False


def test_step_receipt_errors_must_match_open_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["step_receipts"][0]["errors"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("step receipt 0 errors must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]
    assert invalid_report["loops"][0]["step_receipts"][0]["errors"] == ["different_gap"]


def test_closure_report_cannot_claim_terminal_closure() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_closure = invalid_report["loops"][0]["closure_report"]
    invalid_closure["closed"] = True
    invalid_closure["metadata"]["terminal_closure"] = True

    errors = validator.validate_report(invalid_report)

    assert any("closure_report closed must be false" in error for error in errors)
    assert any("terminal_closure must be false" in error for error in errors)
    assert invalid_closure["closed"] is True


def test_closure_report_gaps_must_match_open_blockers() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["closure_report"]["unresolved_gaps"] = ["different_gap"]

    errors = validator.validate_report(invalid_report)

    assert any("unresolved_gaps must match open blockers" in error for error in errors)
    assert invalid_report["loops"][0]["open_blockers"]
    assert invalid_report["loops"][0]["closure_report"]["unresolved_gaps"] == ["different_gap"]


def test_closure_report_evidence_complete_must_match_missing_evidence() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["closure_report"]["evidence_complete"] = True

    errors = validator.validate_report(invalid_report)

    assert any("evidence_complete does not match missing evidence" in error for error in errors)
    assert invalid_report["loops"][0]["missing_evidence"]
    assert invalid_report["loops"][0]["closure_report"]["evidence_complete"] is True


def test_verified_loop_cannot_miss_evidence() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("verified or closed loop cannot miss evidence" in error for error in errors)
    assert invalid_report["loops"][0]["status"] == "verified"
    assert invalid_report["loops"][0]["missing_evidence"]


def test_verified_loop_cannot_miss_authority() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["loops"][0]["status"] = "verified"

    errors = validator.validate_report(invalid_report)

    assert any("verified or closed loop cannot miss authority" in error for error in errors)
    assert invalid_report["loops"][0]["status"] == "verified"
    assert invalid_report["loops"][0]["missing_authority"]


def test_unexpected_report_field_is_reported() -> None:
    report = validator.build_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["extra"] = "forbidden"

    errors = validator.validate_report(invalid_report)

    assert "report has unexpected field: extra" in errors
    assert invalid_report["extra"] == "forbidden"
    assert len(errors) >= 1


def test_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] holistic_loop_read_model_current_output" in streams.out
    assert streams.err == ""


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(json_path, "payload")

    assert json_path.exists()
    assert json_path.name == "payload.json"
