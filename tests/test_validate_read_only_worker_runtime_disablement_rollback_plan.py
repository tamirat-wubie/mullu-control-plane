"""Tests for read-only worker runtime disablement rollback plans.

Purpose: prove rollback plans are bound as evidence without executing
disablement or granting runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_disablement_rollback_plan.
Invariants:
  - Rollback execution remains blocked.
  - Runtime enablement and dispatch remain blocked.
  - The plan keeps trusted runtime clock and operator approval requirements.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_disablement_rollback_plan import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_disablement_rollback_plan,
    main,
    validate_runtime_disablement_rollback_plan,
    write_runtime_disablement_rollback_plan_validation,
)


def test_runtime_disablement_rollback_plan_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_disablement_rollback_plan()

    assert fixture == generated
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert fixture["proof_state"] == "Unknown"
    assert fixture["plan_state"] == "plan_bound_execution_blocked"
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["runtime_disablement_executed"] is False
    assert fixture["runtime_dispatch_performed"] is False
    assert fixture["worker_invocation_performed"] is False
    assert fixture["recovery_state"]["operator_reapproval_required"] is True
    assert fixture["recovery_state"]["trusted_runtime_clock_required"] is True
    assert len(fixture["rollback_steps"]) == 6


def test_runtime_disablement_rollback_plan_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_disablement_rollback_plan_validation.json"
    validation = validate_runtime_disablement_rollback_plan()

    written = write_runtime_disablement_rollback_plan_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.rollback_step_count == 6
    assert validation.required_evidence_ref_count == 9
    assert validation.runtime_enablement_allowed is False
    assert validation.runtime_disablement_executed is False
    assert payload["errors"] == []


def test_runtime_disablement_rollback_plan_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    rollback_plan_path = _write_mutated_rollback_plan(tmp_path)
    payload = json.loads(rollback_plan_path.read_text(encoding="utf-8"))
    payload["runtime_enablement_allowed"] = True
    payload["runtime_dispatch_admitted"] = True
    payload["runtime_dispatch_performed"] = True
    rollback_plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_disablement_rollback_plan(rollback_plan_path=rollback_plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "runtime_dispatch_admitted must be false" in serialized_errors
    assert "runtime_dispatch_performed must be false" in serialized_errors


def test_runtime_disablement_rollback_plan_rejects_rollback_execution_overclaim(tmp_path: Path) -> None:
    rollback_plan_path = _write_mutated_rollback_plan(tmp_path)
    payload = json.loads(rollback_plan_path.read_text(encoding="utf-8"))
    payload["runtime_disablement_executed"] = True
    payload["rollback_steps"][0]["execution_allowed_now"] = True
    payload["recovery_state"]["rollback_execution_allowed"] = True
    rollback_plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_disablement_rollback_plan(rollback_plan_path=rollback_plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "runtime_disablement_executed must be false" in serialized_errors
    assert "rollback step execution_allowed_now must be false" in serialized_errors
    assert "recovery_state.rollback_execution_allowed must be false" in serialized_errors


def test_runtime_disablement_rollback_plan_rejects_step_order_drift(tmp_path: Path) -> None:
    rollback_plan_path = _write_mutated_rollback_plan(tmp_path)
    payload = json.loads(rollback_plan_path.read_text(encoding="utf-8"))
    payload["rollback_steps"][1]["sequence"] = 6
    rollback_plan_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_disablement_rollback_plan(rollback_plan_path=rollback_plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "rollback_steps must preserve sequence 1..6" in serialized_errors
    assert "runtime disablement rollback plan does not match generated plan" in serialized_errors


def test_runtime_disablement_rollback_plan_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_disablement_rollback_plan_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["rollback_step_count"] == 6
    assert stdout_payload["runtime_enablement_allowed"] is False
    assert captured.err == ""


def _write_mutated_rollback_plan(tmp_path: Path) -> Path:
    rollback_plan_path = tmp_path / "runtime_disablement_rollback_plan.json"
    rollback_plan_path.write_text(json.dumps(build_runtime_disablement_rollback_plan()), encoding="utf-8")
    return rollback_plan_path
