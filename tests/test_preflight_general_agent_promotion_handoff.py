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


DEFAULT_ACTION_COUNT = 6
REQUIRED_ENV = {
    "MULLU_BROWSER_SANDBOX_EVIDENCE",
    "MULLU_VOICE_PROBE_AUDIO",
    "OPENAI_API_KEY",
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "MULLU_GATEWAY_URL",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
}


def test_handoff_preflight_blocks_missing_environment_bindings(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "",
    )

    assert report.ready is False
    assert "required environment bindings" in report.blockers
    assert report.step_count == 10
    assert "MULLU_GATEWAY_URL" in report.missing_environment_variables
    assert report.readiness_level == "pilot-governed-core"
    assert report.production_ready is False
    assert any("MULLU_GATEWAY_URL" in step.detail for step in report.steps)
    assert len(report.environment_binding_actions) == len(REQUIRED_ENV)
    gateway_action = next(action for action in report.environment_binding_actions if action.name == "MULLU_GATEWAY_URL")
    assert gateway_action.binding_kind == "url"
    assert gateway_action.risk == "high"
    assert gateway_action.approval_required is False
    assert "handoff_preflight" in gateway_action.required_for
    assert "without printing or serializing" in gateway_action.verification_command
    assert "validate_general_agent_promotion_environment_binding_receipt.py" in gateway_action.verification_command


def test_handoff_preflight_missing_readiness_keeps_report_contract(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, _readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    missing_readiness = tmp_path / "missing-readiness.json"

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=missing_readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is False
    assert report.readiness_level == "pilot-governed-core"
    assert report.production_ready is False
    assert report.blockers == ("promotion readiness report",)


def test_handoff_preflight_accepts_valid_local_state(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert report.checked_at == "2026-05-01T12:00:00+00:00"
    assert report.missing_environment_variables == ()
    assert report.environment_binding_actions == ()
    assert {step.name for step in report.steps} == {
        "operator checklist validation",
        "handoff packet validation",
        "conditional responsibility debt blockers",
        "environment binding contract validation",
        "environment binding receipt validation",
        "required environment bindings",
        "adapter closure schema validation",
        "closure plan schema validation",
        "closure plan drift validation",
        "promotion readiness report",
    }


def test_handoff_preflight_rejects_readiness_count_drift_from_capability_fabric(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    capability_root, capsule_root = _write_minimal_fabric_roots(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        capability_root=capability_root,
        capsule_root=capsule_root,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    step_details = {step.name: step.detail for step in report.steps}

    assert report.ready is False
    assert report.blockers == ("promotion readiness report",)
    assert "expected_capability_count=1" in step_details["promotion readiness report"]
    assert "expected_capsule_count=1" in step_details["promotion readiness report"]
    assert "'capability_count': 81" in step_details["promotion readiness report"]


def test_handoff_preflight_accepts_report_derived_action_count(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path, action_count=12)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
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
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    output_path = tmp_path / "preflight.json"
    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
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
            "--adapter-schema-validation",
            str(adapter_schema_validation),
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
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    drift_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "expected_action_count": DEFAULT_ACTION_COUNT,
                "observed_action_count": DEFAULT_ACTION_COUNT - 1,
                "expected_approval_required_count": 5,
                "observed_approval_required_count": 5,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is False
    assert "closure plan drift validation" in report.blockers
    assert any("observed_action_count" in step.detail for step in report.steps)


def test_handoff_preflight_accepts_matching_generated_action_count(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    generated_action_count = 6
    adapter_schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": 0,
                "approval_required_action_count": 0,
                "blocker_count": 0,
            }
        ),
        encoding="utf-8",
    )
    schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": generated_action_count,
                "approval_required_action_count": 6,
                "source_plan_types": ["deployment", "portfolio"],
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
                "expected_approval_required_count": 6,
                "observed_approval_required_count": 6,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert any("action_count=6" in step.detail for step in report.steps)
    assert any(
        "approval_required_action_count=0" in step.detail
        for step in report.steps
        if step.name == "adapter closure schema validation"
    )


def test_handoff_preflight_rejects_impossible_adapter_approval_count(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    adapter_schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": 3,
                "approval_required_action_count": 6,
                "blocker_count": 3,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    step_details = {step.name: step.detail for step in report.steps}

    assert report.ready is False
    assert report.blockers == ("adapter closure schema validation",)
    assert "approval_required_action_count" in step_details["adapter closure schema validation"]
    assert "'action_count': 3" in step_details["adapter closure schema validation"]


def test_handoff_preflight_accepts_portfolio_source_plan_type(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": 15,
                "approval_required_action_count": 6,
                "source_plan_types": ["adapter", "deployment", "portfolio"],
            }
        ),
        encoding="utf-8",
    )
    drift_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "expected_action_count": 15,
                "observed_action_count": 15,
                "expected_approval_required_count": 6,
                "observed_approval_required_count": 6,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    step_details = {step.name: step.detail for step in report.steps}

    assert report.ready is True
    assert report.blockers == ()
    assert "source_plan_types=['adapter', 'deployment', 'portfolio']" in step_details["closure plan schema validation"]
    assert "expected_approval_required_count=6" in step_details["closure plan drift validation"]


def test_handoff_preflight_rejects_schema_and_drift_count_disagreement(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path, action_count=7)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    drift_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "expected_action_count": 8,
                "observed_action_count": 8,
                "expected_approval_required_count": 5,
                "observed_approval_required_count": 5,
            }
        ),
        encoding="utf-8",
    )

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is False
    assert report.blockers == ("closure plan drift validation",)
    assert any("schema=" in step.detail for step in report.steps)


def test_handoff_preflight_rejects_nonfinite_report_inputs(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    schema_validation.write_text('{"ok": true, "action_count": Infinity}', encoding="utf-8")

    report = preflight_general_agent_promotion_handoff(
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )
    serialized_report = json.dumps(report.as_dict(), sort_keys=True)

    assert report.ready is False
    assert "closure plan schema validation" in report.blockers
    assert "closure plan drift validation" in report.blockers
    assert any("invalid_json_or_empty" in step.detail for step in report.steps)
    assert "Infinity" not in serialized_report


def test_handoff_preflight_rejects_conditional_responsibility_debt_drift(tmp_path: Path) -> None:
    adapter_schema_validation, schema_validation, drift_validation, readiness = _write_valid_reports(tmp_path)
    environment_binding_receipt = _write_valid_environment_binding_receipt(tmp_path)
    checklist_path = tmp_path / "checklist.json"
    checklist = json.loads(Path("examples/general_agent_promotion_operator_checklist.json").read_text(encoding="utf-8"))
    checklist["conditional_approval_blockers"] = []
    checklist_path.write_text(json.dumps(checklist), encoding="utf-8")

    report = preflight_general_agent_promotion_handoff(
        checklist_path=checklist_path,
        environment_binding_receipt_path=environment_binding_receipt,
        adapter_schema_validation_path=adapter_schema_validation,
        schema_validation_path=schema_validation,
        drift_validation_path=drift_validation,
        readiness_path=readiness,
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert report.ready is False
    assert "conditional responsibility debt blockers" in report.blockers
    assert any("conditional responsibility debt blocker drift" in step.detail for step in report.steps)


def _write_valid_reports(
    tmp_path: Path,
    *,
    action_count: int = DEFAULT_ACTION_COUNT,
) -> tuple[Path, Path, Path, Path]:
    adapter_schema_validation = tmp_path / "adapter-schema-validation.json"
    schema_validation = tmp_path / "schema-validation.json"
    drift_validation = tmp_path / "drift-validation.json"
    readiness = tmp_path / "readiness.json"
    adapter_schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": 0,
                "approval_required_action_count": 0,
                "blocker_count": 0,
            }
        ),
        encoding="utf-8",
    )
    schema_validation.write_text(
        json.dumps(
            {
                "ok": True,
                "action_count": action_count,
                "approval_required_action_count": 6,
                "source_plan_types": ["deployment", "portfolio"],
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
                "expected_approval_required_count": 6,
                "observed_approval_required_count": 6,
            }
        ),
        encoding="utf-8",
    )
    readiness.write_text(
        json.dumps(
            {
                "ready": True,
                "readiness_level": "production-general-agent",
                "capability_count": 81,
                "capsule_count": 13,
            }
        ),
        encoding="utf-8",
    )
    return adapter_schema_validation, schema_validation, drift_validation, readiness


def _write_valid_environment_binding_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "environment-binding-receipt.json"
    receipt, errors = emit_general_agent_promotion_environment_binding_receipt(
        env_reader=lambda name: "present" if name in REQUIRED_ENV else "",
    )

    assert errors == ()
    assert receipt.ready is True
    return write_environment_binding_receipt(receipt, receipt_path)


def _write_minimal_fabric_roots(tmp_path: Path) -> tuple[Path, Path]:
    capability_root = tmp_path / "capabilities"
    capsule_root = tmp_path / "capsules"
    pack_dir = capability_root / "agentic_control"
    pack_dir.mkdir(parents=True)
    capsule_root.mkdir()
    (pack_dir / "capability_pack.json").write_text(
        json.dumps(
            {
                "capabilities": [
                    {
                        "capability_id": "agentic_control.test.plan",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (capsule_root / "agentic_control.json").write_text(
        json.dumps(
            {
                "capsule_id": "agentic_control.test",
                "capability_ids": ["agentic_control.test.plan"],
            }
        ),
        encoding="utf-8",
    )
    return capability_root, capsule_root
