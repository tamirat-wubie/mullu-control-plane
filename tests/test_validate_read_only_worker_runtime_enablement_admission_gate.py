"""Tests for read-only worker runtime enablement admission gates.

Purpose: prove accepted evidence does not bypass Foundation Mode runtime
admission blockers.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_enablement_admission_gate.
Invariants:
  - Runtime admission remains denied in Foundation Mode.
  - Runtime enablement remains denied.
  - Admission blockers remain explicit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_admission_gate import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_enablement_admission_gate,
    main,
    validate_runtime_enablement_admission_gate,
    write_runtime_enablement_admission_gate_validation,
)


def test_runtime_enablement_admission_gate_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_enablement_admission_gate()

    assert fixture == generated
    assert fixture["solver_outcome"] == "AwaitingEvidence"
    assert fixture["proof_state"] == "Unknown"
    assert fixture["evidence_accepted"] is True
    assert fixture["runtime_admission_allowed"] is False
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["runtime_dispatch_allowed"] is False
    assert fixture["admission_state"] == "blocked_foundation_mode_runtime_authority_missing"
    assert fixture["summary"]["accepted_evidence_ref_count"] == 12
    assert fixture["summary"]["admission_blocker_count"] == 3


def test_runtime_enablement_admission_gate_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_enablement_admission_gate_validation.json"
    validation = validate_runtime_enablement_admission_gate()

    written = write_runtime_enablement_admission_gate_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.accepted_evidence_ref_count == 12
    assert validation.admission_blocker_count == 3
    assert validation.runtime_admission_allowed is False
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_enablement_admission_gate_rejects_runtime_overclaim(tmp_path: Path) -> None:
    gate_path = _write_mutated_gate(tmp_path)
    payload = json.loads(gate_path.read_text(encoding="utf-8"))
    payload["runtime_admission_allowed"] = True
    payload["runtime_enablement_allowed"] = True
    payload["runtime_dispatch_allowed"] = True
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_admission_gate(gate_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "runtime_admission_allowed must be false" in serialized_errors
    assert "runtime_enablement_allowed must be false" in serialized_errors
    assert "runtime_dispatch_allowed must be false" in serialized_errors


def test_runtime_enablement_admission_gate_rejects_blocker_drift(tmp_path: Path) -> None:
    gate_path = _write_mutated_gate(tmp_path)
    payload = json.loads(gate_path.read_text(encoding="utf-8"))
    payload["admission_blockers"] = payload["admission_blockers"][:-1]
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_admission_gate(gate_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "admission_blockers must match Foundation Mode blockers" in serialized_errors
    assert "runtime enablement admission gate does not match generated" in serialized_errors
    assert validation.runtime_admission_allowed is False


def test_runtime_enablement_admission_gate_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_enablement_admission_gate_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["admission_blocker_count"] == 3
    assert captured.err == ""


def _write_mutated_gate(tmp_path: Path) -> Path:
    gate_path = tmp_path / "runtime_enablement_admission_gate.json"
    gate_path.write_text(json.dumps(build_runtime_enablement_admission_gate()), encoding="utf-8")
    return gate_path
