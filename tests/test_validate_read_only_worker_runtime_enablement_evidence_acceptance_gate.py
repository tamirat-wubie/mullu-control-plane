"""Tests for read-only worker runtime enablement evidence acceptance gates.

Purpose: prove accepted evidence refs do not grant runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_enablement_evidence_acceptance_gate.
Invariants:
  - Evidence acceptance is not runtime admission.
  - Runtime enablement remains denied.
  - Authority grant refs remain empty.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_evidence_acceptance_gate import (  # noqa: E402
    DEFAULT_EXAMPLE,
    build_runtime_enablement_evidence_acceptance_gate,
    main,
    validate_runtime_enablement_evidence_acceptance_gate,
    write_runtime_enablement_evidence_acceptance_gate_validation,
)


def test_runtime_enablement_evidence_acceptance_gate_fixture_matches_generated_projection() -> None:
    fixture = json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))
    generated = build_runtime_enablement_evidence_acceptance_gate()

    assert fixture == generated
    assert fixture["solver_outcome"] == "SolvedVerified"
    assert fixture["proof_state"] == "Pass"
    assert fixture["evidence_accepted"] is True
    assert fixture["authority_granted"] is False
    assert fixture["runtime_admission_allowed"] is False
    assert fixture["runtime_enablement_allowed"] is False
    assert fixture["runtime_dispatch_allowed"] is False
    assert fixture["summary"]["accepted_evidence_ref_count"] == 12
    assert fixture["summary"]["authority_grant_count"] == 0


def test_runtime_enablement_evidence_acceptance_gate_validator_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "runtime_enablement_evidence_acceptance_gate_validation.json"
    validation = validate_runtime_enablement_evidence_acceptance_gate()

    written = write_runtime_enablement_evidence_acceptance_gate_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.accepted_evidence_ref_count == 12
    assert validation.authority_grant_count == 0
    assert validation.runtime_admission_allowed is False
    assert validation.runtime_enablement_allowed is False
    assert payload["errors"] == []


def test_runtime_enablement_evidence_acceptance_gate_rejects_authority_overclaim(tmp_path: Path) -> None:
    gate_path = _write_mutated_gate(tmp_path)
    payload = json.loads(gate_path.read_text(encoding="utf-8"))
    payload["authority_granted"] = True
    payload["runtime_admission_allowed"] = True
    payload["authority_grant_refs"] = ["examples/read_only_worker_phi_gov_dispatch_authorization_witness.foundation.json"]
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_evidence_acceptance_gate(gate_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "authority_granted must be false" in serialized_errors
    assert "runtime_admission_allowed must be false" in serialized_errors
    assert "authority_grant_refs must remain empty" in serialized_errors


def test_runtime_enablement_evidence_acceptance_gate_rejects_ref_drift(tmp_path: Path) -> None:
    gate_path = _write_mutated_gate(tmp_path)
    payload = json.loads(gate_path.read_text(encoding="utf-8"))
    payload["accepted_evidence_refs"] = payload["accepted_evidence_refs"][:-1]
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_runtime_enablement_evidence_acceptance_gate(gate_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.valid is False
    assert "accepted_evidence_refs must match reviewed evidence refs" in serialized_errors
    assert "runtime enablement evidence acceptance gate does not match generated" in serialized_errors
    assert validation.runtime_enablement_allowed is False


def test_runtime_enablement_evidence_acceptance_gate_cli_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "runtime_enablement_evidence_acceptance_gate_validation.json"

    exit_code = main(["--output", str(output_path), "--write", "--json"])
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["valid"] is True
    assert written_payload["valid"] is True
    assert stdout_payload["accepted_evidence_ref_count"] == 12
    assert captured.err == ""


def _write_mutated_gate(tmp_path: Path) -> Path:
    gate_path = tmp_path / "runtime_enablement_evidence_acceptance_gate.json"
    gate_path.write_text(json.dumps(build_runtime_enablement_evidence_acceptance_gate()), encoding="utf-8")
    return gate_path
