"""Tests for Agentic Service Harness authority transition validation.

Purpose: prove harness contract fixtures remain planning-only authority
transitions before UI, mutation endpoints, persistence adapters, external
adapter execution, branch writes, pull-request creation, or high-risk action
authority are implemented.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_authority_transitions.
Invariants:
  - Read-only and dry-run transitions are non-effectful.
  - Branch-write and open-PR transitions remain pending approval.
  - High-risk transitions remain blocked.
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
    BLOCKED_HIGH_RISK_ACTIONS,
    DEFAULT_EXAMPLES,
    EXPECTED_SCENARIOS,
)
from scripts.validate_agentic_service_harness_authority_transitions import (  # noqa: E402
    main,
    validate_agentic_service_harness_authority_transitions,
    write_authority_transition_validation,
)


def test_authority_transitions_accept_default_contract_fixtures() -> None:
    validation = validate_agentic_service_harness_authority_transitions()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.scenario_count == len(EXPECTED_SCENARIOS)
    assert validation.transition_count == len(DEFAULT_EXAMPLES)
    assert validation.blocked_high_risk_action_count == len(BLOCKED_HIGH_RISK_ACTIONS)
    assert all(path.startswith("examples/agentic_service_harness.") for path in validation.source_paths)


def test_authority_transition_rejects_approved_branch_gate(tmp_path: Path) -> None:
    payload = _default_payload("agentic_service_harness.branch_write_awaiting_approval.json")
    payload["approval_gates"][0]["status"] = "approved"
    payload["approval_gates"][0]["permits_external_effect"] = True
    source_path = _write_source(tmp_path, payload)

    validation = validate_agentic_service_harness_authority_transitions(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "gate gate.branchwrite status must be pending" in serialized_errors
    assert "cannot be terminal or approved" in serialized_errors
    assert "must not permit external effect" in serialized_errors


def test_authority_transition_rejects_dry_run_file_change(tmp_path: Path) -> None:
    payload = _default_payload("agentic_service_harness.dry_run.json")
    payload["receipts"][0]["files_changed"]["changed_file_count"] = 1
    payload["receipts"][0]["files_changed"]["changed_file_refs"] = ["src/app.py"]
    payload["result_summaries"][0]["changed_file_count"] = 1
    source_path = _write_source(tmp_path, payload)

    validation = validate_agentic_service_harness_authority_transitions(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "receipt changed_file_count must remain 0" in serialized_errors
    assert "receipt changed_file_refs must remain empty" in serialized_errors
    assert "summary changed_file_count must remain 0" in serialized_errors


def test_authority_transition_rejects_open_pr_without_branch_evidence(tmp_path: Path) -> None:
    payload = _default_payload("agentic_service_harness.open_pr_awaiting_approval.json")
    payload["result_summaries"][0]["blockers"] = ["approval_required"]
    payload["repository_connections"][0]["write_authority_enabled"] = True
    source_path = _write_source(tmp_path, payload)

    validation = validate_agentic_service_harness_authority_transitions(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "open_pr summary must list branch_evidence_required" in serialized_errors
    assert "repository write authority must remain false" in serialized_errors
    assert "source contract" in serialized_errors


def test_authority_transition_rejects_incomplete_high_risk_block(tmp_path: Path) -> None:
    payload = _default_payload("agentic_service_harness.blocked_high_risk.json")
    payload["agent_runs"][0]["blocked_actions"].remove("deploy")
    payload["permission_model"]["can_deploy"] = True
    source_path = _write_source(tmp_path, payload)

    validation = validate_agentic_service_harness_authority_transitions(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "blocked high-risk run missing" in serialized_errors
    assert "permission_model.can_deploy must remain false" in serialized_errors
    assert "source contract" in serialized_errors


def test_authority_transition_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "authority-transition-validation.json"
    validation = validate_agentic_service_harness_authority_transitions()

    written = write_authority_transition_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["transition_count"] == len(DEFAULT_EXAMPLES)


def _default_payload(filename: str) -> dict[str, object]:
    path = next(path for path in DEFAULT_EXAMPLES if path.name == filename)
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))


def _write_source(tmp_path: Path, payload: dict[str, object]) -> Path:
    source_path = tmp_path / "agentic_service_harness.source.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    return source_path
