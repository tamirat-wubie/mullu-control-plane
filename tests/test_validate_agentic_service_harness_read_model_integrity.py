"""Tests for Agentic Service Harness read-model identity integrity.

Purpose: prove harness read-model projections preserve source contract
identity links across projects, runs, approvals, receipts, evidence, and result
summaries.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_model_integrity.
Invariants:
  - Default contract fixtures produce identity-consistent read models.
  - Broken run, receipt, evidence, project, and duplicate identity links fail
    closed.
  - CLI validation writes a deterministic non-terminal receipt.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_contract import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_SCENARIOS,
)
from scripts.validate_agentic_service_harness_read_model_integrity import (  # noqa: E402
    main,
    validate_agentic_service_harness_read_model_integrity,
    write_read_model_integrity_validation,
)
from scripts.validate_agentic_service_harness_read_model_projections import (  # noqa: E402
    project_contract_to_read_model,
)


def test_read_model_integrity_accepts_default_contract_fixtures() -> None:
    validation = validate_agentic_service_harness_read_model_integrity()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.source_count == len(DEFAULT_EXAMPLES)
    assert validation.projection_count == len(DEFAULT_EXAMPLES)
    assert validation.scenario_count == len(EXPECTED_SCENARIOS)
    assert validation.checked_link_count > 0


def test_read_model_integrity_rejects_run_receipt_drift(monkeypatch) -> None:
    original_projector = project_contract_to_read_model

    def mismatched_receipt_projector(contract: dict[str, object], contract_ref: str) -> dict[str, object]:
        projection = original_projector(contract, contract_ref)
        projection["runs"][0]["receipt_id"] = "receipt.missing"
        return projection

    monkeypatch.setattr(
        "scripts.validate_agentic_service_harness_read_model_integrity.project_contract_to_read_model",
        mismatched_receipt_projector,
    )
    validation = validate_agentic_service_harness_read_model_integrity()
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt missing" in serialized_errors
    assert "receipt_id mismatch" in serialized_errors


def test_read_model_integrity_rejects_project_run_ref_drift(monkeypatch) -> None:
    original_projector = project_contract_to_read_model

    def mismatched_project_run_projector(contract: dict[str, object], contract_ref: str) -> dict[str, object]:
        projection = original_projector(contract, contract_ref)
        projection["projects"][0]["agent_run_ids"] = ["run.unlinked"]
        return projection

    monkeypatch.setattr(
        "scripts.validate_agentic_service_harness_read_model_integrity.project_contract_to_read_model",
        mismatched_project_run_projector,
    )
    validation = validate_agentic_service_harness_read_model_integrity()
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "agent_run_ids mismatch" in serialized_errors
    assert "run.unlinked" in serialized_errors


def test_read_model_integrity_rejects_receipt_evidence_drift(monkeypatch) -> None:
    original_projector = project_contract_to_read_model

    def mismatched_evidence_projector(contract: dict[str, object], contract_ref: str) -> dict[str, object]:
        projection = original_projector(contract, contract_ref)
        projection["receipts"][0]["evidence_refs"] = ["evidence://missing"]
        return projection

    monkeypatch.setattr(
        "scripts.validate_agentic_service_harness_read_model_integrity.project_contract_to_read_model",
        mismatched_evidence_projector,
    )
    validation = validate_agentic_service_harness_read_model_integrity()
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt/evidence refs mismatch" in serialized_errors
    assert "evidence://missing" in serialized_errors


def test_read_model_integrity_rejects_duplicate_projected_run_ids(monkeypatch) -> None:
    original_projector = project_contract_to_read_model

    def duplicate_run_projector(contract: dict[str, object], contract_ref: str) -> dict[str, object]:
        projection = original_projector(contract, contract_ref)
        projection["runs"].append(deepcopy(projection["runs"][0]))
        return projection

    monkeypatch.setattr(
        "scripts.validate_agentic_service_harness_read_model_integrity.project_contract_to_read_model",
        duplicate_run_projector,
    )
    validation = validate_agentic_service_harness_read_model_integrity()
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "duplicate run_id" in serialized_errors
    assert "projected runs" in serialized_errors


def test_read_model_integrity_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "read-model-integrity-validation.json"
    validation = validate_agentic_service_harness_read_model_integrity()

    written = write_read_model_integrity_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["scenario_count"] == len(EXPECTED_SCENARIOS)
    assert captured.err == ""
