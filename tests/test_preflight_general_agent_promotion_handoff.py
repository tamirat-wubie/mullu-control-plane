"""Tests for general-agent promotion handoff preflight."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_general_agent_promotion_environment_binding_receipt import (
    emit_general_agent_promotion_environment_binding_receipt,
    write_environment_binding_receipt,
)
from scripts.preflight_general_agent_promotion_handoff import (
    main,
    preflight_general_agent_promotion_handoff,
    write_handoff_preflight_report,
)


DEFAULT_ACTION_COUNT = 14
REQUIRED_ENV = {
    "MULLU_BROWSER_SANDBOX_EVIDENCE",
    "MULLU_VOICE_PROBE_AUDIO",
    "MULLU_GATEWAY_URL",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
}


def test_handoff_preflight_blocks_missing_environment_bindings(tmp_path: Path) -> None:
    schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "",
    )

    assert report.ready is False
    assert "required environment bindings" in report.blockers
    assert report.step_count == 8
    assert "MULLU_GATEWAY_URL" in report.missing_environment_variables
    assert report.readiness_level == "pilot-governed-core"
    assert report.production_ready is False
    assert any("MULLU_GATEWAY_URL" in step.detail for step in report.steps)


def test_handoff_preflight_accepts_valid_local_state(tmp_path: Path) -> None:
    schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert report.checked_at == "2026-05-01T12:00:00+00:00"
    assert report.missing_environment_variables == ()
    assert {step.name for step in report.steps} == {
        "operator checklist validation",
        "handoff packet validation",
        "environment binding contract validation",
        "environment binding receipt validation",
        "required environment bindings",
        "closure plan schema validation",
        "closure plan drift validation",
        "promotion readiness report",
    }


def test_handoff_preflight_accepts_report_derived_action_count(tmp_path: Path) -> None:
    schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path, action_count=12)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    step_details = {step.name: step.detail for step in report.steps}

    assert report.ready is True
    assert "action_count=12" in step_details["closure plan schema validation"]
    assert "expected_action_count=12" in step_details["closure plan drift validation"]


def test_handoff_preflight_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    output_path = tmp_path / "preflight.json"
    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "",
    )

    written = write_handoff_preflight_report(report, output_path)
    exit_code = main(
        [
            "--schema-validation",
            str(schema_validation),
            "--drift-validation",
            str(drift_validation),
            "--readiness",
            str(readiness),
            "--environment-binding-receipt",
            str(environment_binding_receipt),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 2
    assert payload["ready"] is False
    assert stdout_payload["ready"] is False
    assert "missing_environment_variables" in payload


def test_handoff_preflight_rejects_drift_count_mismatch(tmp_path: Path) -> None:
    schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    drift_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "expected_action_count": DEFAULT_ACTION_COUNT,
                "observed_action_count": DEFAULT_ACTION_COUNT - 1,
                "expected_approval_required_count": 4,
                "observed_approval_required_count": 4,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is False
    assert "closure plan drift validation" in report.blockers
    assert any("observed_action_count" in step.detail for step in report.steps)


def test_handoff_preflight_accepts_matching_generated_action_count(tmp_path: Path) -> None:
    schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    generated_action_count = 7
    schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": generated_action_count,
                "approval_required_action_count": 4,
                "source_plan_types": ["adapter", "deployment"],
            }
        ),
        encoding="utf-8",
    )
    drift_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "expected_action_count": generated_action_count,
                "observed_action_count": generated_action_count,
                "expected_approval_required_count": 4,
                "observed_approval_required_count": 4,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert any("action_count=7" in step.detail for step in report.steps)


def _write_valid_reports(
    tmp_path: Path,
    *,
    action_count: int = DEFAULT_ACTION_COUNT,
) -> tuple[Path, Path, Path]:
    schema_validation = tmp_path / "schema-validation.json"
    drift_validation = tmp_path / "drift-validation.json"
    readiness = tmp_path / "readiness.json"
    schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": action_count,
                "approval_required_action_count": 4,
                "source_plan_types": ["adapter", "deployment"],
            }
        ),
        encoding="utf-8",
    )
    drift_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "expected_action_count": action_count,
                "observed_action_count": action_count,
                "expected_approval_required_count": 4,
                "observed_approval_required_count": 4,
            }
        ),
        encoding="utf-8",
    )
    readiness.write_text(
        json.dumps(
            {
                "ready": False,
                "readiness_level": "pilot-governed-core",
                "capability_count": 52,
                "capsule_count": 10,
            }
        ),
        encoding="utf-8",
    )
    return schema_validation, drift_validation, readiness


def _write_valid_environment_binding_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "environment-binding-receipt.json"
    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert errors == ()
    assert receipt.ready is True
    return write_environment_binding_receipt(receipt, receipt_path)
