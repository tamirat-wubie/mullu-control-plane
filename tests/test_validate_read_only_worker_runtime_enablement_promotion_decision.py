"""Tests for read-only worker runtime enablement promotion decisions.

Purpose: prove promotion decisions deny runtime activation under Foundation
Mode while preserving accepted evidence refs for future re-entry.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_enablement_promotion_decision.
Invariants:
  - Runtime promotion remains denied.
  - Runtime enablement remains denied.
  - Re-entry evidence remains explicit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_promotion_decision import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_enablement_promotion_decision,
    main,
    validate_runtime_enablement_promotion_decision,
    write_runtime_enablement_promotion_decision_validation,
)


def test_runtime_enablement_promotion_decision_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_enablement_promotion_decision()

    assert fixture == generated
    assert fixture["solver_outcome"] == "GovernanceBlocked"
    assert fixture["proof_state"] == "Pass"
    assert fixture["runtime_promotion_decided"] is True
    assert fixture["runtime_promotion_allowed"] is False
    assert fixture["runtime_promotion_denied"] is True
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["summary"]["accepted_evidence_ref_count"] == 12
    assert fixture["summary"]["runtime_promotion_allowed_count"] == 0


def test_runtime_enablement_promotion_decision_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_enablement_promotion_decision_validation.json"
    validation = validate_runtime_enablement_promotion_decision()

    written = write_runtime_enablement_promotion_decision_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.accepted_evidence_ref_count == 12
    assert validation.runtime_promotion_allowed is False
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_enablement_promotion_decision_rejects_promotion_overclaim(tmp_path: Path) -> None:
    decision_path = _write_mutated_decision(tmp_path)
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    payload["runtime_promotion_allowed"] = True
    payload["runtime_enablement_allowed"] = True
    payload["runtime_dispatch_allowed"] = True
    decision_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_promotion_decision(decision_path=decision_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "runtime_promotion_allowed must be false" in serialized_errors
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "runtime_dispatch_allowed must be false" in serialized_errors


def test_runtime_enablement_promotion_decision_rejects_denial_reason_drift(tmp_path: Path) -> None:
    decision_path = _write_mutated_decision(tmp_path)
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    payload["denial_reasons"] = payload["denial_reasons"][:-1]
    payload["summary"]["denial_reason_count"] = 2
    decision_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_promotion_decision(decision_path=decision_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "denial_reasons must match Foundation Mode promotion denial reasons" in serialized_errors
    assert "runtime enablement promotion decision does not match generated" in serialized_errors
    assert validation.runtime_enablement_allowed is False


def test_runtime_enablement_promotion_decision_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_enablement_promotion_decision_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["accepted_evidence_ref_count"] == 12
    assert captured.err == ""


def _write_mutated_decision(tmp_path: Path) -> Path:
    decision_path = tmp_path / "runtime_enablement_promotion_decision.json"
    decision_path.write_text(json.dumps(build_runtime_enablement_promotion_decision()), encoding="utf-8")
    return decision_path
