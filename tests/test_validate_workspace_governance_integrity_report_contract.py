"""Purpose: verify workspace governance integrity report contract validation.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.validate_workspace_governance_integrity_report_contract.
Invariants:
  - Schema, example, and current output share the same report contract.
  - Counts derive from artifact records.
  - Malformed digest, closure, and extra-field evidence is rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_workspace_governance_integrity_report_contract as validator


def test_current_integrity_report_contract_passes() -> None:
    errors = validator.validate_contract()
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")

    assert errors == []
    assert schema["title"] == "Workspace Governance Integrity Report"
    assert validator.DEFAULT_EXAMPLE_PATH.exists()
    assert validator.DEFAULT_WITNESS_PATH.exists()


def test_current_report_has_consistent_counts() -> None:
    report = validator.build_current_report()
    errors = validator.validate_report(report)

    assert errors == []
    assert report["report_id"] == "workspace_governance_integrity"
    assert report["artifact_count"] == report["hashed_count"]
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True


def test_count_mismatch_is_reported() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["hashed_count"] = 0

    errors = validator.validate_report(invalid_report)

    assert any("hashed_count does not match" in error for error in errors)
    assert invalid_report["hashed_count"] == 0
    assert invalid_report["status"] == "passed"


def test_invalid_digest_is_reported() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["artifacts"][0]["sha256"] = "not-a-digest"

    errors = validator.validate_report(invalid_report)

    assert any("sha256 must be null" in error for error in errors)
    assert invalid_report["artifacts"][0]["sha256"] == "not-a-digest"
    assert invalid_report["artifacts"][0]["exists"] is True


def test_failed_missing_artifact_report_can_be_valid() -> None:
    report = {
        "report_id": "workspace_governance_integrity",
        "status": "failed",
        "artifact_count": 1,
        "hashed_count": 0,
        "missing_count": 1,
        "issue_count": 1,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "artifacts": [
            {
                "name": "missing_artifact",
                "path": "docs/missing.json",
                "purpose": "Synthetic missing artifact record.",
                "exists": False,
                "size_bytes": None,
                "sha256": None,
                "issue": "referenced file does not exist",
            }
        ],
    }

    errors = validator.validate_report(report)

    assert errors == []
    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1


def test_terminal_closure_flag_drift_is_reported() -> None:
    report = validator.build_current_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["terminal_closure_required"] = False

    errors = validator.validate_report(invalid_report)

    assert "terminal_closure_required must be true" in errors
    assert invalid_report["terminal_closure_required"] is False
    assert invalid_report["report_is_not_terminal_closure"] is True


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(payload_path, "payload")

    assert payload_path.exists()
    assert payload_path.name == "payload.json"
