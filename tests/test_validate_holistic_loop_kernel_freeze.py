"""Purpose: verify the holistic loop kernel v1 freeze validator.
Governance scope: golden fixture parity, report/schema/HTTP parity, v1
    extension policy, and proof witness anchoring.
Dependencies: scripts.validate_holistic_loop_kernel_freeze.
Invariants:
  - Current v1 freeze validation passes.
  - Golden fixture drift is reported explicitly.
  - HTTP parity drift is reported explicitly.
  - Holistic witness labels cannot become unanchored.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import validate_holistic_loop_kernel_freeze as validator


def test_holistic_loop_kernel_freeze_contract_passes() -> None:
    errors = validator.validate_freeze_contract()
    fixture = validator.load_json_object(validator.DEFAULT_FIXTURE_PATH, "fixture")
    report = validator.build_report()

    assert errors == []
    assert fixture == report
    assert report["report_id"] == validator.REPORT_ID
    assert report["terminal_closure_required"] is True


def test_golden_snapshot_drift_is_reported(tmp_path: Path) -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    report = validator.build_report()
    stale_fixture = copy.deepcopy(report)
    stale_fixture["loops"][0]["open_blockers"] = []
    fixture_path = tmp_path / "stale_holistic_loop_read_model_v1_golden.json"
    fixture_path.write_text(json.dumps(stale_fixture, sort_keys=True), encoding="utf-8")

    errors = validator.validate_golden_snapshot(
        report,
        validator.load_json_object(fixture_path, "stale fixture"),
        schema,
    )

    assert "golden fixture does not match current report" in errors
    assert any("missing evidence lacks blocker" in error for error in errors)
    assert stale_fixture["loops"][0]["open_blockers"] == []


def test_http_payload_normalizes_to_report_contract() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    report = validator.build_report()
    http_payload = validator.fetch_http_payload()
    normalized = validator.normalize_http_payload(http_payload)

    errors = validator.validate_payload_parity(report, http_payload, schema)

    assert errors == []
    assert normalized == report
    assert http_payload["read_model_version"] == validator.READ_MODEL_VERSION
    assert http_payload["read_only"] is True


def test_http_payload_parity_drift_is_reported() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    report = validator.build_report()
    http_payload = validator.fetch_http_payload()
    http_payload["read_model_version"] = "holistic_loop_kernel.v2"
    http_payload["loops"] = []

    errors = validator.validate_payload_parity(report, http_payload, schema)

    assert "HTTP payload read_model_version does not match v1 contract" in errors
    assert "HTTP payload does not normalize to the current report" in errors
    assert http_payload["loops"] == []


def test_kernel_v1_policy_doc_contains_freeze_rules() -> None:
    doc_text = validator.DEFAULT_DOC_PATH.read_text(encoding="utf-8")
    errors = validator.validate_kernel_policy_doc(doc_text)

    assert errors == []
    assert "v1 additive-only" in doc_text
    assert "Extension Checklist" in doc_text


def test_kernel_v1_policy_doc_drift_is_reported() -> None:
    errors = validator.validate_kernel_policy_doc("Kernel v1 Stability Boundary")

    assert any("v1 additive-only" in error for error in errors)
    assert any("Extension Checklist" in error for error in errors)
    assert len(errors) >= 2


def test_holistic_loop_witness_integrity_has_zero_unanchored_labels() -> None:
    errors = validator.validate_holistic_witness_integrity()

    assert errors == []
    assert validator.HOLISTIC_SURFACE_ID == "holistic_loop_read_model_kernel"
    assert validator.READ_MODEL_VERSION == "holistic_loop_kernel.v1"


def test_holistic_loop_witness_integrity_rejects_unanchored_labels() -> None:
    matrix = validator.proof_coverage_matrix()
    holistic_surface = next(
        surface
        for surface in matrix["surfaces"]
        if surface["surface_id"] == validator.HOLISTIC_SURFACE_ID
    )
    holistic_surface["runtime_witnesses"].append("unanchored_freeze_regression")

    errors = validator.validate_holistic_witness_integrity(matrix)

    assert "holistic loop proof surface has unanchored witness labels" in errors
    assert "holistic loop proof surface lists unanchored witnesses" in errors
    assert "holistic loop proof surface runtime witnesses must all have exact anchors" in errors
