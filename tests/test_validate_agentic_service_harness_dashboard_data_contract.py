"""Tests for Agentic Service Harness dashboard data contract.

Purpose: prove future dashboard data remains read-only, display-only,
source-bound, and non-terminal before UI or route work is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_dashboard_data_contract.
Invariants:
  - Valid foundation examples pass schema and semantic validation.
  - Section drift, UI/action enablement, missing source contracts, mutation
    route strings, and secret-like payloads fail closed.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_dashboard_data_contract import (  # noqa: E402
    DEFAULT_EXAMPLES,
    EXPECTED_SECTIONS,
    main,
    validate_agentic_service_harness_dashboard_data_contract,
    write_dashboard_data_contract_validation,
)


def test_dashboard_data_contract_accepts_default_example() -> None:
    validation = validate_agentic_service_harness_dashboard_data_contract()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.example_count == 1
    assert validation.section_count == len(EXPECTED_SECTIONS)
    assert validation.schema_path == "schemas/agentic_service_harness_dashboard_data_contract.schema.json"
    assert validation.example_paths == (
        "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    )
    payload = _default_payload()
    assert [section["section_id"] for section in payload["dashboard_sections"]] == list(EXPECTED_SECTIONS)
    assert payload["readiness_gates"]["missing_evidence_policy"] == "AwaitingEvidence"
    assert payload["authority_denials"]["terminal_closure"] is False


def test_dashboard_data_contract_rejects_section_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["dashboard_sections"][0]["section_id"] = "run_status"
    payload["dashboard_sections"][0]["source_refs"] = []
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "dashboard_sections must match ordered sections" in serialized_errors
    assert "duplicate section_id" in serialized_errors
    assert "must declare source_refs" in serialized_errors


def test_dashboard_data_contract_rejects_ui_and_action_enablement(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["contract_scope"]["ui_created"] = True
    payload["readiness_gates"]["ui_build_admitted"] = True
    payload["dashboard_sections"][2]["action_buttons_enabled"] = True
    payload["authority_denials"]["task_creation_route_admitted"] = True
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "ui_created" in serialized_errors
    assert "ui_build_admitted" in serialized_errors
    assert "action_buttons_enabled" in serialized_errors
    assert "task_creation_route_admitted" in serialized_errors


def test_dashboard_data_contract_rejects_missing_source_ref(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["source_contract_refs"].remove("schemas/agentic_service_harness_read_models.schema.json")
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing source_contract_refs" in serialized_errors
    assert "schemas/agentic_service_harness_read_models.schema.json" in serialized_errors
    assert validation.example_count == 1


def test_dashboard_data_contract_rejects_mutation_route_string(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["next_action"] = "Forbidden route: POST /api/v1/harness/dashboard/tasks"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert "next_action" in serialized_errors


def test_dashboard_data_contract_rejects_secret_like_payload(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["contract_scope"]["access_token_value"] = "github_pat_forbiddencredential"
    example_path = _write_example(tmp_path, payload)

    validation = validate_agentic_service_harness_dashboard_data_contract(example_paths=(example_path,))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden secret-bearing key" in serialized_errors
    assert "credential-like value" in serialized_errors


def test_dashboard_data_contract_writer_and_cli_honor_strict(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "dashboard-data-contract-validation.json"
    validation = validate_agentic_service_harness_dashboard_data_contract()

    written = write_dashboard_data_contract_validation(validation, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["section_count"] == len(EXPECTED_SECTIONS)


def _default_payload() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))


def _write_example(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "agentic_service_harness_dashboard_data_contract.foundation.json"
    example_path.write_text(json.dumps(payload), encoding="utf-8")
    return example_path
