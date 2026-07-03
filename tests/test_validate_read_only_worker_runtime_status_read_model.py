"""Tests for the read-only worker runtime status read model."""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_status_read_model import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_status_read_model,
    main,
    validate_runtime_status_read_model,
    write_runtime_status_read_model_validation,
)


def test_runtime_status_read_model_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_status_read_model()

    assert fixture == generated
    assert fixture["read_model_version"] == "read_only_worker_runtime_status_read_model.v1"
    assert fixture["projection_scope"]["projection_mode"] == "FOUNDATION_STATUS_PROJECTION"
    assert fixture["operator_status"]["foundation_closure_complete"] is True
    assert fixture["operator_status"]["live_runtime_blocked"] is True
    assert fixture["runtime_status"]["evidence_acceptance_state"] == "accepted_for_foundation_review"
    assert fixture["runtime_status"]["runtime_admission_state"] == "denied"
    assert fixture["runtime_status"]["runtime_promotion_state"] == "denied_foundation_mode"
    assert fixture["authority_denials"]["runtime_enablement_allowed"] is False
    assert fixture["summary"]["accepted_evidence_ref_count"] == 12


def test_runtime_status_read_model_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_status_read_model_validation.json"
    validation = validate_runtime_status_read_model()

    written = write_runtime_status_read_model_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.foundation_closure_complete is True
    assert validation.live_runtime_blocked is True
    assert validation.runtime_admission_allowed is False
    assert validation.runtime_promotion_allowed is False
    assert validation.runtime_enablement_allowed is False
    assert validation.runtime_dispatch_allowed is False
    assert payload["errors"] == []


def test_runtime_status_read_model_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    read_model_path = _write_mutated_read_model(tmp_path)
    payload = json.loads(read_model_path.read_text(encoding="utf-8"))
    payload["authority_denials"]["runtime_admission_allowed"] = True
    payload["authority_denials"]["runtime_enablement_allowed"] = True
    payload["authority_denials"]["runtime_dispatch_allowed"] = True
    payload["authority_denials"]["receipt_append_allowed"] = True
    payload["authority_denials"]["secret_values_serialized"] = True
    read_model_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_status_read_model(read_model_path=read_model_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "authority_denials.runtime_admission_allowed must be false" in serialized_errors
    assert "authority_denials.runtime_enablement_allowed must be false" in serialized_errors
    assert "authority_denials.runtime_dispatch_allowed must be false" in serialized_errors
    assert "authority_denials.receipt_append_allowed must be false" in serialized_errors
    assert "authority_denials.secret_values_serialized must be false" in serialized_errors


def test_runtime_status_read_model_rejects_projection_scope_drift(tmp_path: Path) -> None:
    read_model_path = _write_mutated_read_model(tmp_path)
    payload = json.loads(read_model_path.read_text(encoding="utf-8"))
    payload["projection_scope"]["source_runtime_invocation_performed"] = True
    payload["projection_scope"]["raw_secret_values_included"] = True
    payload["operator_status"]["live_runtime_blocked"] = False
    read_model_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_status_read_model(read_model_path=read_model_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "source_runtime_invocation_performed must be false" in serialized_errors
    assert "raw_secret_values_included must be false" in serialized_errors
    assert "operator_status.live_runtime_blocked must be true" in serialized_errors


def test_runtime_status_read_model_rejects_summary_and_ref_drift(tmp_path: Path) -> None:
    read_model_path = _write_mutated_read_model(tmp_path)
    payload = json.loads(read_model_path.read_text(encoding="utf-8"))
    payload["evidence_refs"] = ["schemas/read_only_worker_runtime_status_read_model.schema.json"]
    payload["summary"]["chain_ref_count"] = 1
    payload["summary"]["blocked_authority_count"] = 1
    read_model_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_status_read_model(read_model_path=read_model_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "evidence_refs missing required ref" in serialized_errors
    assert "summary.chain_ref_count must match runtime status projection" in serialized_errors
    assert "summary.blocked_authority_count must match runtime status projection" in serialized_errors


def test_runtime_status_read_model_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_status_read_model_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["runtime_enablement_allowed"] is False
    assert stdout_payload["runtime_dispatch_allowed"] is False
    assert captured.err == ""


def _write_mutated_read_model(tmp_path: Path) -> Path:
    read_model_path = tmp_path / "runtime_status_read_model.json"
    read_model_path.write_text(json.dumps(build_runtime_status_read_model()), encoding="utf-8")
    return read_model_path
