"""Tests for Agentic Service Harness read-model fixture projections.

Purpose: prove all harness contract fixtures can be deterministically projected
into read-only read models without introducing UI, mutation endpoints,
persistence adapters, external adapter execution, branch writes, pull-request
creation, secret serialization, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_model_projections.
Invariants:
  - Every contract scenario projects to one schema-valid read-model envelope.
  - Source write authority, mutation route strings, missing scenarios, and
    terminal projection claims fail closed.
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
from scripts.validate_agentic_service_harness_read_model_projections import (  # noqa: E402
    main,
    project_contract_to_read_model,
    validate_agentic_service_harness_read_model_projections,
    write_projection_validation,
)


def test_read_model_projections_accept_all_default_contract_fixtures() -> None:
    validation = validate_agentic_service_harness_read_model_projections()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.source_count == len(DEFAULT_EXAMPLES)
    assert validation.projection_count == len(DEFAULT_EXAMPLES)
    assert validation.scenario_count == len(EXPECTED_SCENARIOS)
    assert validation.schema_path == "schemas/agentic_service_harness_read_models.schema.json"
    assert all(path.startswith("examples/agentic_service_harness.") for path in validation.source_paths)


def test_projected_read_only_contract_preserves_core_refs() -> None:
    source_path = next(path for path in DEFAULT_EXAMPLES if path.name.endswith("read_only.json"))
    source = json.loads(source_path.read_text(encoding="utf-8"))

    projection = project_contract_to_read_model(source, source_path.as_posix())

    assert projection["projection_scope"]["read_only"] is True
    assert projection["projection_scope"]["mutation_endpoints_admitted"] is False
    assert projection["runs"][0]["run_id"] == source["agent_runs"][0]["run_id"]
    assert projection["runs"][0]["executes_adapter"] is False
    assert projection["receipts"][0]["receipt_is_not_terminal_closure"] is True
    assert projection["receipts"][0]["terminal_closure"] is False
    assert projection["workspace_allocations"][0]["sandbox_id"] == source["workspace_sandboxes"][0]["sandbox_id"]
    assert projection["workspace_allocations"][0]["workspace_created"] is False
    assert projection["workspace_allocations"][0]["commands_executed"] is False
    assert projection["durable_entity_bindings"]["read_only"] is True
    assert projection["durable_entity_bindings"]["entity_bindings"][0]["read_model_source"] == "fixture_projection"
    assert projection["permission_snapshot"]["can_merge"] is False
    assert projection["repositories"][0]["installation_ref"] == source["repository_connections"][0]["installation_ref"]
    assert projection["repositories"][0]["permission_scopes"] == source["repository_connections"][0]["permission_scopes"]
    assert projection["repositories"][0]["revocation_state"] == "not_revoked"


def test_projected_open_pr_contract_preserves_approval_request_binding() -> None:
    source_path = next(path for path in DEFAULT_EXAMPLES if path.name.endswith("open_pr_awaiting_approval.json"))
    source = json.loads(source_path.read_text(encoding="utf-8"))

    projection = project_contract_to_read_model(source, source_path.as_posix())

    approval = projection["approvals"][0]
    source_gate = source["approval_gates"][0]
    assert approval["approval_request_id"] == source_gate["approval_request_id"]
    assert approval["approval_request_ref"] == source_gate["approval_request_ref"]
    assert approval["gateway_approval_ref"] == source_gate["gateway_approval_ref"]
    assert approval["requested_evidence_ref"] == "approval://openpr-required"
    assert approval["decision_required"] == "operator_response_required"
    assert approval["response_record_required"] is True
    assert approval["response_record_collected"] is False
    assert approval["approval_collected"] is False
    assert approval["authority_granted"] is False
    assert approval["permits_external_effect"] is False
    approval_binding = next(
        binding
        for binding in projection["durable_entity_bindings"]["entity_bindings"]
        if binding["entity_kind"] == "ApprovalRequest"
    )
    assert approval_binding["primary_key"] == "approval_request_id"
    assert "gateway_approval_ref" in approval_binding["owner_ref_fields"]


def test_read_model_projection_rejects_source_write_authority(tmp_path: Path) -> None:
    payload = _default_payload("agentic_service_harness.branch_write_awaiting_approval.json")
    payload["repository_connections"][0]["write_authority_enabled"] = True
    source_path = _write_source(tmp_path, payload)

    validation = validate_agentic_service_harness_read_model_projections(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source repository write authority must remain false" in serialized_errors
    assert "source scenarios missing" in serialized_errors


def test_read_model_projection_rejects_source_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload("agentic_service_harness.read_only.json")
    payload["next_action"] = "Forbidden route: POST /api/harness/tasks"
    source_path = _write_source(tmp_path, payload)

    validation = validate_agentic_service_harness_read_model_projections(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source mutation route string" in serialized_errors
    assert "source contract" in serialized_errors


def test_read_model_projection_detects_terminal_projection_claim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _default_payload("agentic_service_harness.read_only.json")
    source_path = _write_source(tmp_path, payload)

    original_projector = project_contract_to_read_model

    def terminal_projector(contract: dict[str, object], contract_ref: str) -> dict[str, object]:
        projection = original_projector(contract, contract_ref)
        projection["receipts"][0]["terminal_closure"] = True
        return projection

    monkeypatch.setattr(
        "scripts.validate_agentic_service_harness_read_model_projections.project_contract_to_read_model",
        terminal_projector,
    )
    validation = validate_agentic_service_harness_read_model_projections(source_paths=(source_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure" in serialized_errors
    assert "must be false" in serialized_errors


def test_read_model_projection_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "projection-validation.json"
    validation = validate_agentic_service_harness_read_model_projections()

    written = write_projection_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["projection_count"] == len(DEFAULT_EXAMPLES)


def _default_payload(filename: str) -> dict[str, object]:
    path = next(path for path in DEFAULT_EXAMPLES if path.name == filename)
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))


def _write_source(tmp_path: Path, payload: dict[str, object]) -> Path:
    source_path = tmp_path / "agentic_service_harness.source.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    return source_path
